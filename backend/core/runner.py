#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""One agent run.

This is what an agent's crontab executes, and what the "run now" button starts
through the privileged daemon. It always runs as `agent-xxx`, never as root and
never as the web user, which is what makes `bash.run` safe: the tool does not
have to drop privileges, because the whole process never had any.

The loop is the standard agentic one - ask the model, run the tools it asks
for, feed the results back - with three ceilings around it, all read from the
agent's own info.json:

  max_steps_per_run    : how many times the model may be asked
  max_tokens_per_run   : total tokens the run may spend
  timeout_seconds      : wall clock

The ceilings exist because these agents run unattended on a schedule. A loop
with no ceiling on a paid provider is an open invoice, and on a self-hosted one
it is a machine that never gives the GPU back.

A run started from the chat is the same loop with two differences: the previous
exchanges are replayed so the agent remembers the conversation, and the answer
is written back to the chat history. It does not count against the daily run
ceiling - that ceiling exists to stop an unattended cron job, not to stop you
typing.

A run a due card asked for is in between: it writes its answer back to the chat
too, because the card was announced there the moment the run started, but its
prompt is the card and not a conversation, so nothing is replayed. That is what
`--turn-id` without `--chat-message` means. Such a run is a scheduled one, so
the daily ceiling does apply - and when it stops the run, the chat is told,
because a card that was announced and then silently skipped reads as an agent
that ignored it.

Usage:
  runner.py --agent-id 007 [--prompt "..."] [--dry-run]
  runner.py --agent-id 007 --chat-message "..." --turn-id abc123
  runner.py --agent-id 007 --prompt "Card #12 is due: ..." --turn-id abc123
"""

import argparse
import json
import os
import sys
import time
import uuid

# Cron starts this by PATH, not as a module, so the directory Python puts on
# sys.path is backend/core/ and `import backend` finds nothing. The daemon
# sets PYTHONPATH when it starts an agent, which is why a run from the web or
# from the buzzer always worked and every scheduled run died on the first
# import - with the traceback going to cron's mail, which on a LAN box goes
# nowhere.
#
# Fixed here rather than only in the crontab, because the crontabs of agents
# that already exist are already written: this makes them work again on the
# next update, without rewriting anything.
sys.path.insert(0, os.path.dirname(os.path.dirname(
  os.path.dirname(os.path.abspath(__file__)))))

from backend.core import agent_api_client
from backend.core import chat
from backend.core import memory
from backend.core import paths
from backend.core import run_journal
from backend.core import skills
from backend.core import tool_registry
from backend.providers import base as providers_base
from backend.providers import factory

# What the agent is told when its crontab wakes it up with nothing specific to
# do. Deliberately short, for two reasons: the real instructions belong in
# system-prompt.md, and this text is prepended to a prompt the user may have
# written in any language - the more English the system adds, the more the
# agent drifts into answering in English rather than in theirs.
cDefaultWakeUpPrompt = (
  "You have been woken up by your schedule. Check the kanban board, continue "
  "the work that is yours, and stop when there is nothing useful left to do."
)

# What the agent is told when a ceiling stops it mid-task. Kept as short as the
# wake-up prompt, and for the same reason.
cClosingPrompt = "Budget spent. Answer now with what you already have."

# How long that closing answer may be. Note what this does NOT cap: the call
# still resends the whole conversation, so its prompt costs whatever the run
# has accumulated - on a long tool-heavy run that can be as much again as the
# ceiling itself. It is worth it, because a run that spends its whole budget
# gathering facts and then says nothing has wasted every token it spent, but it
# does mean a stopped run can end up costing more than its ceiling.
cClosingTokenBudget = 1000

# Ceilings that leave the agent holding an unwritten answer. The time ceiling
# is not one of them: the run is already late, and a further call would make it
# later still.
lCeilingsWorthClosing = ["steps", "tokens"]

# Why a run ended before it asked the model anything. What travels into the chat
# is the name and not a sentence, the same as a ceiling: the interface writes the
# sentence, in the language the user reads.
cReasonDisabled = "disabled"
cReasonDailyCeiling = "daily_ceiling"


def fLogLine(pMessage):
  """Write one timestamped line to stderr, which cron mails and systemd logs."""
  sys.stderr.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pMessage))
  sys.stderr.flush()


def fReadOwnInfo(pAgentId):
  """Read this agent's info.json from its own home directory."""
  vInfoPath = paths.fGetAgentInfoPath(pAgentId)
  try:
    with open(vInfoPath, "r", encoding="utf-8") as vFile:
      return json.load(vFile)
  except OSError as vError:
    raise RuntimeError("Cannot read %s: %s" % (vInfoPath, vError))
  except ValueError as vError:
    raise RuntimeError("%s is not valid JSON: %s" % (vInfoPath, vError))


def fReadOwnSystemPrompt(pAgentId):
  """Read this agent's system-prompt.md."""
  vPromptPath = paths.fGetAgentSystemPromptPath(pAgentId)
  try:
    with open(vPromptPath, "r", encoding="utf-8") as vFile:
      return vFile.read()
  except OSError:
    return ""


# One line per language, written IN that language.
#
# The wording matters as much as the setting: a line of English added by the
# system pushes the model towards answering in English, which is the whole
# problem this exists to fix. So the instruction to answer in Spanish is
# itself in Spanish.
#
# It also has to say that it WINS. Every shipped prompt carries "answer in the
# language this prompt is written in, and in the user's if they write to you
# in another" - so a line that only states a preference is a second opinion
# next to a rule, and the model followed the rule. Measured: with
# "Responde siempre en español." alone, the agent answered in English.
#
# Short otherwise, for the reason every injected line here is short: the real
# instructions belong in the agent's own prompt, and each sentence the system
# adds is paid for on every call of every run.
dAnswerLanguageLines = {
  "en-GB": "Always answer in English, even if these instructions or the "
           "message are in another language. This overrides any rule above "
           "about which language to answer in.",
  "en-US": "Always answer in English, even if these instructions or the "
           "message are in another language. This overrides any rule above "
           "about which language to answer in.",
  "es-AR": "Respondé siempre en español, aunque estas instrucciones o el "
           "mensaje estén en otro idioma. Esto tiene prioridad sobre "
           "cualquier regla de más arriba sobre en qué idioma responder.",
  "es-ES": "Responde siempre en español, aunque estas instrucciones o el "
           "mensaje estén en otro idioma. Esto tiene prioridad sobre "
           "cualquier regla de más arriba sobre en qué idioma responder.",
  "de-DE": "Antworte immer auf Deutsch, auch wenn diese Anweisungen oder die "
           "Nachricht in einer anderen Sprache sind. Das hat Vorrang vor jeder "
           "Regel weiter oben dazu, in welcher Sprache zu antworten ist.",
  "fr-FR": "Réponds toujours en français, même si ces instructions ou le "
           "message sont dans une autre langue. Cela prime sur toute règle "
           "ci-dessus concernant la langue de réponse.",
  "hi-IN": "हमेशा हिन्दी में जवाब दो, चाहे ये निर्देश या संदेश किसी और "
           "भाषा में हों। ऊपर लिखे किसी भी नियम से, कि किस भाषा में जवाब "
           "देना है, यह नियम ऊपर रहेगा।",
  "it-IT": "Rispondi sempre in italiano, anche se queste istruzioni o il "
           "messaggio sono in un'altra lingua. Questo ha la precedenza su "
           "qualsiasi regola qui sopra su in che lingua rispondere.",
  "pt-BR": "Responda sempre em português do Brasil, mesmo que estas instruções "
           "ou a mensagem estejam em outro idioma. Isto tem prioridade sobre "
           "qualquer regra acima sobre em que idioma responder.",
  "pt-PT": "Responde sempre em português de Portugal, mesmo que estas "
           "instruções ou a mensagem estejam noutro idioma. Isto tem "
           "prioridade sobre qualquer regra acima sobre em que idioma "
           "responder.",
  "ru-RU": "Всегда отвечай по-русски, даже если эти инструкции или сообщение "
           "написаны на другом языке. Это правило важнее любого правила выше "
           "о том, на каком языке отвечать.",
  "ja-JP": "これらの指示やメッセージが別の言語で書かれていても、必ず日本語で答えて"
           "ください。これは、どの言語で答えるかについて上に書かれたどのルールよりも"
           "優先されます。",
  "zh-CN": "请始终用简体中文回答，即使这些指示或消息是用其他语言写的。这一条优先于"
           "上面关于用什么语言回答的任何规则。",
  "ko-KR": "이 지시나 메시지가 다른 언어로 쓰여 있더라도 항상 한국어로 답하세요. "
           "이 규칙은 어떤 언어로 답할지에 대해 위에 적힌 어떤 규칙보다 우선합니다.",
}


def fReadAnswerLanguageLine(pAgentId):
  """The line telling this agent which language to answer in, or "".

  Asked of the agent API because the setting lives in the web application's
  database and an agent cannot open it. A run must not fail because that
  question could not be answered: with no answer the agent keeps doing what it
  did before, which is to answer in the language of its own prompt.
  """
  try:
    dResult = agent_api_client.fSendRequest(
      "who_am_i", fReadOwnApiToken(pAgentId))
  except Exception:
    return ""
  return dAnswerLanguageLines.get(str(dResult.get("answer_language") or ""), "")


def fBuildSystemPrompt(pAgentId, pAgentInfo=None):
  """Return the system prompt with the agent's memory in front of it.

  The memory goes into the system prompt rather than into the conversation so
  that it is there on the very first call of every run - an agent that has to
  ask for its own memory has already started without it.

  The skills come after the memory and say only what each one is for. Their
  bodies are fetched with skill.read, by an agent that decided it needs one,
  because a procedure resent on every call of every run costs more than the
  work it describes.

  The language line goes last, after the agent's own rules: a run woken by
  cron has no other way of knowing what language to answer in. Nobody wrote to
  it, and the interface's own language is a preference in somebody's browser
  that the server never sees.
  """
  vPrompt = fReadOwnSystemPrompt(pAgentId)
  vMemory = memory.fBuildPromptSection(pAgentId)
  if vMemory:
    vPrompt = "%s\n\n%s" % (vPrompt.rstrip("\n"), vMemory)

  dInfo = pAgentInfo if pAgentInfo is not None else fReadOwnInfo(pAgentId)
  vSkills = skills.fBuildPromptSection(dInfo.get("skills"))
  if vSkills:
    vPrompt = "%s\n\n%s" % (vPrompt.rstrip("\n"), vSkills)

  vLanguageLine = fReadAnswerLanguageLine(pAgentId)
  if vLanguageLine:
    vPrompt = "%s\n\n%s" % (vPrompt.rstrip("\n"), vLanguageLine)
  return vPrompt


def fReadOwnApiToken(pAgentId):
  """Read this agent's local API token."""
  vTokenPath = paths.fGetAgentApiTokenPath(pAgentId)
  try:
    with open(vTokenPath, "r", encoding="utf-8") as vFile:
      return vFile.read().strip()
  except OSError:
    return ""


def fReadApiKey(pAgentId, pProviderName):
  """Return the API key for this agent's provider.

  Self-hosted providers need none. For the cloud ones, in order:

    1. A key in the agent's own home, keys/<provider>.key. That one wins, which
       is how a single agent gets billed to a different account.
    2. The shared key set in Settings, fetched through the agent API. It lives
       where no agent can read it, and the API only hands over the key for the
       provider this agent is configured with.
    3. Nothing, and the adapter falls back to the environment - which is what
       lets an operator test a provider by hand.
  """
  if factory.fIsSelfHosted(pProviderName):
    return ""

  vKeyPath = os.path.join(
    paths.fGetAgentHome(pAgentId), "keys", "%s.key" % (pProviderName,)
  )
  try:
    with open(vKeyPath, "r", encoding="utf-8") as vFile:
      vKey = vFile.read().strip()
      if vKey:
        return vKey
  except OSError:
    pass

  try:
    return agent_api_client.fGetApiKey(pAgentId, pProviderName)
  except agent_api_client.AgentApiClientError as vError:
    fLogLine("No shared key for %s: %s" % (pProviderName, vError))
    return ""


def fNewRunId():
  """Return an identifier for one run, unique across agents and restarts."""
  return uuid.uuid4().hex


def fSelectAllowedTools(pAgentInfo, pTools):
  """Return the names of the tools this agent may use.

  An agent with the kanban switched off does not get the kanban tools, which is
  the whole mechanism: a tool the model is never shown is a tool it cannot call
  and cannot be talked into calling.
  """
  lAllowed = [str(vName) for vName in pAgentInfo.get("tools") or []]
  if not pAgentInfo.get("kanban_enabled", True):
    lAllowed = [vName for vName in lAllowed if not vName.startswith("kanban.")]
  return [vName for vName in lAllowed if vName in pTools]


class AgentRun:
  """One bounded conversation between an agent and its model."""

  def __init__(self, pAgentId, pPrompt="", pDryRun=False, pChatMessage="",
               pTurnId=""):
    self.vAgentId = paths.fNormalizeAgentId(pAgentId)
    self.vPrompt = pPrompt or cDefaultWakeUpPrompt
    self.vDryRun = pDryRun
    # A chat run carries the conversation and replays it to the model.
    self.vChatMessage = str(pChatMessage or "")
    self.vTurnId = str(pTurnId or "")
    self.vIsChat = bool(self.vChatMessage)
    # Whether the answer is written back into the chat. Not the same question: a
    # card that came due opens a turn in the chat and is answered there, but its
    # prompt is the card, so there is no conversation to replay.
    self.vWritesToChat = bool(self.vTurnId)

    self.dInfo = fReadOwnInfo(self.vAgentId)
    self.vSystemPrompt = fBuildSystemPrompt(self.vAgentId, self.dInfo)
    self.dLimits = self.dInfo.get("limits") or {}
    self.vStartedAt = time.time()
    self.vTokensSpent = 0
    # Which tools this run actually called. It decides whether a run nobody
    # asked for is worth putting in the chat: one that changed something has
    # a report, one that only looked has a journal entry.
    self.lToolsUsed = []
    self.vStepsTaken = 0
    self.vRunId = None
    # Which ceiling ended the run, if one did. The user is told: a run that
    # stops here has an answer half written, and saying nothing about it is
    # what makes it look like the agent simply gave up.
    self.vCeilingHit = ""
    # Whether this run has already fallen back to the backup model. Once per
    # run: if the backup fails too, the run fails.
    self.vUsingFallback = False

    self.dTools, self.lToolErrors = tool_registry.fLoadAllTools()
    self.lAllowedToolNames = fSelectAllowedTools(self.dInfo, self.dTools)
    self.vContext = tool_registry.ToolContext(
      self.vAgentId, self.dInfo, fReadOwnApiToken(self.vAgentId)
    )

  @property
  def vMaxSteps(self):
    """Maximum number of model calls this run may make."""
    return int(self.dLimits.get("max_steps_per_run", 25))

  @property
  def vMaxTokens(self):
    """Maximum number of tokens this run may spend in total."""
    return int(self.dLimits.get("max_tokens_per_run", 16384))

  @property
  def vTimeoutSeconds(self):
    """Wall clock ceiling for this run."""
    return int(self.dLimits.get("timeout_seconds", 300))

  @property
  def vMaxRunsPerDay(self):
    """Maximum number of runs this agent may start in one day."""
    return int(self.dLimits.get("max_runs_per_day", 48))

  def fCheckCeilings(self):
    """Return which ceiling stopped the run, or an empty string to continue.

    The name is what the interface shows the user, in their own language, so
    it is one of a fixed set rather than a sentence.
    """
    if self.vStepsTaken >= self.vMaxSteps:
      return "steps"
    if self.vTokensSpent >= self.vMaxTokens:
      return "tokens"
    vElapsed = time.time() - self.vStartedAt
    if vElapsed >= self.vTimeoutSeconds:
      return "time"
    return ""

  def fDescribeCeiling(self, pCeiling):
    """Return the ceiling and its value, for the log and the journal."""
    dLimits = {
      "steps": self.vMaxSteps,
      "tokens": self.vMaxTokens,
      "time": self.vTimeoutSeconds,
    }
    return "%s ceiling reached (%s)" % (pCeiling, dLimits.get(pCeiling, "?"))

  def fBuildProvider(self):
    """Build the provider adapter for this agent."""
    dProviderConfig = self.dInfo.get("provider") or {}
    vProviderName = dProviderConfig.get("name", "")
    return factory.fBuildProvider(
      dProviderConfig,
      pApiKey=fReadApiKey(self.vAgentId, vProviderName),
      pTimeoutSeconds=self.vTimeoutSeconds,
    )

  def fBuildFallbackProvider(self):
    """Build the backup adapter, or None when the agent has no backup.

    Built lazily, only once the main one has failed: an agent that never needs
    its backup should not need it to be configurable, reachable, or paid for.
    """
    dFallbackConfig = self.dInfo.get("fallback_provider") or {}
    vProviderName = str(dFallbackConfig.get("name") or "").strip()
    if not vProviderName:
      return None
    return factory.fBuildProvider(
      dFallbackConfig,
      pApiKey=fReadApiKey(self.vAgentId, vProviderName),
      pTimeoutSeconds=self.vTimeoutSeconds,
    )

  def fSwitchToFallback(self, pError):
    """Return the backup provider after the main one failed, or None.

    Switching happens once per run. If the backup fails too, the run fails:
    trying each in turn for ever would burn the ceilings on a provider outage
    and still have nothing to show.
    """
    if self.vUsingFallback:
      return None
    vFallback = None
    try:
      vFallback = self.fBuildFallbackProvider()
    except Exception as vBuildError:
      fLogLine("The backup model cannot be built either: %s" % (vBuildError,))
      return None
    if vFallback is None:
      return None

    self.vUsingFallback = True
    fLogLine("Main provider failed (%s). Falling back to %s."
             % (pError, vFallback.fDescribe()))
    run_journal.fRecordFallback(
      self.vAgentId, self.vRunId, vFallback.cProviderName, vFallback.vModel,
      str(pError)
    )
    return vFallback

  def fExecute(self):
    """Run the loop. Returns the final text the agent produced."""
    if not self.dInfo.get("enabled", True):
      fLogLine("Agent %s is disabled. Nothing to do." % (self.vAgentId,))
      # A turn that nothing will ever answer has to be closed here. Left open,
      # the interface waits for an answer for ever and the composer stays shut.
      self.fRecordChatFailure(
        "This agent is switched off, so the card it was woken for was not acted "
        "on.",
        cReasonDisabled
      )
      return ""

    # The daily ceiling guards against an unattended schedule, so a message the
    # user just typed is not subject to it: they are watching, and a chat that
    # silently stops answering would be worse than the spending it prevents.
    if not self.vIsChat:
      vRunsToday = run_journal.fCountRunsOn(self.vAgentId)
      if vRunsToday >= self.vMaxRunsPerDay:
        fLogLine(
          "Agent %s has already run %d times today (ceiling %d). Skipping."
          % (self.vAgentId, vRunsToday, self.vMaxRunsPerDay)
        )
        self.fRecordChatFailure(
          "This agent has already run %d times today, which is its daily "
          "ceiling, so it did not act on this card. Raise it under Model."
          % (vRunsToday,),
          cReasonDailyCeiling
        )
        return ""

    for vToolError in self.lToolErrors:
      fLogLine("Tool warning: %s" % (vToolError,))

    vProvider = self.fBuildProvider()
    lToolSchemas = tool_registry.fBuildToolSchemas(self.dTools, self.lAllowedToolNames)

    fLogLine(
      "Agent %s starting on %s with %d tools: %s"
      % (self.vAgentId, vProvider.fDescribe(), len(lToolSchemas),
         ", ".join(self.lAllowedToolNames) or "none")
    )

    if self.vDryRun:
      fLogLine("Dry run: not calling the model.")
      return ""

    self.vRunId = fNewRunId()
    run_journal.fRecordRunStarted(
      self.vAgentId, self.vRunId, vProvider.cProviderName, vProvider.vModel
    )
    if self.vIsChat:
      lMessages = chat.fBuildConversationForModel(self.vAgentId, self.vChatMessage)
    else:
      lMessages = [{"role": "user", "content": self.vPrompt}]
    vFinalText = ""

    try:
      while True:
        vStopReason = self.fCheckCeilings()
        if vStopReason:
          self.vCeilingHit = vStopReason
          fLogLine("Stopping: %s" % (self.fDescribeCeiling(vStopReason),))
          break

        try:
          vResponse = self.fAskModel(vProvider, lMessages, lToolSchemas)
        except providers_base.ProviderError as vError:
          # The main provider will not answer. Try the backup once, from this
          # same step: the conversation so far is replayed to it, so the work
          # already done is not thrown away.
          vFallback = self.fSwitchToFallback(vError)
          if vFallback is None:
            raise
          vProvider = vFallback
          vResponse = self.fAskModel(vProvider, lMessages, lToolSchemas)

        self.vStepsTaken += 1
        self.vTokensSpent += vResponse.vTotalTokens
        run_journal.fRecordUsage(
          self.vAgentId, self.vRunId, vProvider.cProviderName, vProvider.vModel,
          vResponse.vPromptTokens, vResponse.vCompletionTokens
        )

        if vResponse.vText:
          vFinalText = vResponse.vText

        if vResponse.vStopReason == providers_base.cStopRefusal:
          fLogLine("The model refused the request. Stopping.")
          break

        if not vResponse.lToolCalls:
          fLogLine(
            "Done after %d steps and %d tokens."
            % (self.vStepsTaken, self.vTokensSpent)
          )
          break

        lMessages.append({
          "role": "assistant",
          "content": vResponse.vText,
          "tool_calls": vResponse.lToolCalls,
        })
        lMessages.extend(self.fRunToolCalls(vResponse.lToolCalls))

      if self.vCeilingHit in lCeilingsWorthClosing:
        vFinalText = self.fAskForClosingAnswer(
          vProvider, lMessages, vFinalText)

      vStatus = "stopped" if self.vCeilingHit else "finished"
      run_journal.fRecordRunFinished(
        self.vAgentId, self.vRunId, vStatus,
        self.vStepsTaken, self.vTokensSpent,
        self.fDescribeCeiling(self.vCeilingHit) if self.vCeilingHit else "",
        vFinalText
      )
      self.fRecordChatAnswer(vFinalText)
      self.fReportUnaskedRun(vStatus, vFinalText)
    except providers_base.ProviderError as vError:
      fLogLine("Provider error: %s" % (vError,))
      run_journal.fRecordRunFinished(
        self.vAgentId, self.vRunId, "failed",
        self.vStepsTaken, self.vTokensSpent, str(vError), vFinalText
      )
      self.fRecordChatFailure(vError)
      self.fReportUnaskedRun("failed", vFinalText, str(vError))
      raise
    except Exception as vError:
      fLogLine("Run failed: %s" % (vError,))
      run_journal.fRecordRunFinished(
        self.vAgentId, self.vRunId, "failed",
        self.vStepsTaken, self.vTokensSpent, str(vError), vFinalText
      )
      self.fRecordChatFailure(vError)
      self.fReportUnaskedRun("failed", vFinalText, str(vError))
      raise
    finally:
      run_journal.fTrimJournal(self.vAgentId)

    return vFinalText

  def fAskForClosingAnswer(self, pProvider, pMessages, pTextSoFar):
    """Ask once more, with no tools, for the answer the ceiling interrupted.

    A run that spends its whole budget calling tools and then stops leaves the
    user with whatever the agent happened to say on its way in - usually "I am
    going to check", which reads as an agent that did nothing. The facts are
    already in the conversation; this turns them into the answer they were
    gathered for, for a bounded extra cost and with no tools, so the agent
    cannot start more work it has no budget to finish.
    """
    fLogLine("Asking for a closing answer after the %s ceiling."
             % (self.vCeilingHit,))
    lClosing = list(pMessages)
    lClosing.append({"role": "user", "content": cClosingPrompt})
    try:
      vResponse = pProvider.fSendMessages(
        self.vSystemPrompt, lClosing, [], cClosingTokenBudget
      )
    except Exception as vError:
      # The run is over either way; a failure here must not lose the text the
      # agent did produce.
      fLogLine("The closing answer failed: %s" % (vError,))
      return pTextSoFar

    # Counted in tokens but not in steps: what it cost is what the user is
    # shown and must be true, while the step ceiling measures the work the
    # agent did and this call is not work, it is the report on it.
    self.vTokensSpent += vResponse.vTotalTokens
    run_journal.fRecordUsage(
      self.vAgentId, self.vRunId, pProvider.cProviderName, pProvider.vModel,
      vResponse.vPromptTokens, vResponse.vCompletionTokens
    )
    return vResponse.vText or pTextSoFar

  def fRecordChatAnswer(self, pText):
    """Write the agent's answer back to the chat history."""
    if not self.vWritesToChat:
      return
    vText = pText or "(the agent finished without saying anything)"
    dMetadata = {"steps": self.vStepsTaken, "tokens": self.vTokensSpent}
    # The interface turns this into a sentence in the user's own language, so
    # what travels is which ceiling it was, not a phrase in English.
    if self.vCeilingHit:
      dMetadata["ceiling"] = self.vCeilingHit
    chat.fAppendMessage(
      self.vAgentId, chat.cRoleAgent, vText, self.vTurnId,
      pMetadata=dMetadata
    )
    chat.fTrimHistory(self.vAgentId)

  def fRecordChatFailure(self, pError, pReason=""):
    """Write a failure into the chat, so the user is never left waiting.

    Without this a failed run leaves the question marked pending for ever and
    the interface spins with nothing to show.

    `pReason` names the cause when it is the system's own decision rather than
    something a provider said, so the interface can put the sentence in the
    user's language. The English text still goes in the file, for whoever reads
    chat.jsonl with no interface around it.
    """
    if not self.vWritesToChat:
      return
    chat.fAppendMessage(
      self.vAgentId, chat.cRoleError, str(pError), self.vTurnId,
      pMetadata={"reason": pReason} if pReason else None
    )
    chat.fTrimHistory(self.vAgentId)

  def fReportUnaskedRun(self, pStatus, pText, pError=""):
    """Put the report of a run nobody asked for where it will be read.

    A run started from the chat, or for a card that came due, already closes
    its turn there. A run started by the agent's own crontab had nowhere to
    put its answer at all: it went to standard output, which cron mails to a
    local mailbox that on a LAN box nobody ever opens. The agent did the work,
    wrote it up, and the text was dropped.

    The journal now keeps every one of them. This adds the second half: the
    ones worth interrupting somebody with go into the conversation as well -
    a run that changed something, and a run that did not finish. A run that
    only looked at things stays in the journal, or an agent on an hourly
    crontab would post twelve "nothing to report" messages a day.
    """
    if self.vWritesToChat or self.vIsChat:
      return
    if not chat.fIsRunWorthReporting(pStatus, self.lToolsUsed):
      return

    vReport = str(pText or "").strip()
    if not vReport:
      vReport = str(pError or "")
    if not vReport:
      return

    chat.fAppendRunMessage(
      self.vAgentId, vReport,
      "failed" if pStatus != "finished" else "changed",
      self.lToolsUsed
    )
    chat.fTrimHistory(self.vAgentId)

  def fAskModel(self, pProvider, pMessages, pToolSchemas):
    """Ask the model once, never letting one reply blow the run's budget."""
    vRemainingTokens = max(512, self.vMaxTokens - self.vTokensSpent)
    return pProvider.fSendMessages(
      self.vSystemPrompt, pMessages, pToolSchemas, vRemainingTokens
    )

  def fRunToolCalls(self, pToolCalls):
    """Run every tool the model asked for and return the result messages.

    All results are returned together, in the order they were requested: a
    provider that gets them piecemeal learns to stop asking for several tools
    at once, which makes every later run slower.
    """
    lResults = []
    for vCall in pToolCalls:
      fLogLine("Tool call: %s(%s)" % (vCall.vName, json.dumps(vCall.dArguments)[:200]))
      vResultText, vIsError = tool_registry.fRunTool(
        self.dTools, self.lAllowedToolNames, vCall.vName,
        vCall.dArguments, self.vContext
      )
      if not vIsError:
        # Only the ones that worked: a card that failed to be created is not
        # something to tell the user about in the conversation.
        self.lToolsUsed.append(vCall.vName)
      if vIsError:
        fLogLine("Tool %s failed: %s" % (vCall.vName, vResultText[:200]))
      lResults.append({
        "role": "tool",
        "tool_call_id": vCall.vCallId,
        "name": vCall.vName,
        "content": vResultText,
        "is_error": vIsError,
      })
    return lResults


def fParseArguments(pArgumentList):
  """Parse the command line."""
  vParser = argparse.ArgumentParser(description="Run one Bunch of AIgents agent.")
  vParser.add_argument("--agent-id", required=True, help="Agent id, 000 to 999.")
  vParser.add_argument("--prompt", default="", help="What to ask the agent to do.")
  vParser.add_argument(
    "--dry-run", action="store_true",
    help="Load everything and report what would run, without calling the model."
  )
  vParser.add_argument(
    "--chat-message", default="",
    help="Answer this message as a chat turn, replaying the conversation."
  )
  vParser.add_argument(
    "--turn-id", default="",
    help="Identifier tying the answer to the question in the chat history. On "
         "its own, with --prompt, it answers a card announced in the chat."
  )
  return vParser.parse_args(pArgumentList)


def fMain(pArgumentList=None):
  """Entry point used by cron and by the privileged daemon."""
  dArguments = fParseArguments(pArgumentList if pArgumentList is not None else sys.argv[1:])
  try:
    vRun = AgentRun(
      dArguments.agent_id, dArguments.prompt, dArguments.dry_run,
      dArguments.chat_message, dArguments.turn_id
    )
    vFinalText = vRun.fExecute()
  except ValueError as vError:
    fLogLine("Invalid argument: %s" % (vError,))
    return 2
  except Exception as vError:
    fLogLine("Run aborted: %s" % (vError,))
    if dArguments.turn_id:
      # The run never started, so nothing else will close this turn - whether it
      # was opened by a typed message or by a card that came due.
      try:
        chat.fAppendMessage(
          dArguments.agent_id, chat.cRoleError, str(vError), dArguments.turn_id
        )
      except Exception:
        pass
    return 1
  if vFinalText:
    sys.stdout.write(vFinalText + "\n")
  return 0


if __name__ == "__main__":
  sys.exit(fMain())
