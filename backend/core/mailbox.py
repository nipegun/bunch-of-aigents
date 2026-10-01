"""One mailbox, reachable over IMAP, that agents act on through the agent API.

The same arrangement as channels, and for the same reason: an agent that could
read the mailbox password would not have "access to the inbox", it would have
the account - every message in it, for ever, and the ability to send as its
owner. So the credentials live in the web application's own database, which is
0700 to `boa`, and an agent asks the agent API to read, delete, move or forward
on its behalf. It learns what came back and nothing else.

Talked to with `imaplib` and `smtplib` from the standard library. A mail client
would be another dependency on a machine that is meant to be a Debian box with
Python on it, and the four things this needs to do are four IMAP commands.

Two decisions worth stating, because both are the kind that look like an
inconvenience until the day they are not:

  - **Deleting really deletes.** IMAP's own model is a flag plus an expunge,
    and a "delete" that only sets a flag would be a delete that the user cannot
    see the result of. So the message is moved to the account's Trash folder
    when there is one, and only expunged outright when there is not. What an
    agent removes, a person can still find.

  - **Forwarding is allowed only to addresses the user listed.** A mailbox is
    read by an agent whose instructions arrive, in part, inside the messages it
    reads. Anything else is one convincing email away from mailing the whole
    inbox somewhere else. The list is checked HERE, in the process that sends,
    not described in a prompt: a rule in a prompt is advice, a rule at the
    socket is a rule.
"""

import email
import email.header
import email.message
import email.utils
import imaplib
import re
import smtplib
import ssl

from backend.core import db

# Settings keys. They live beside the SMTP ones, in the web application's
# database: agents cannot read that file.
cSettingImapHost = "imap_host"
cSettingImapPort = "imap_port"
cSettingImapUser = "imap_user"
cSettingImapPassword = "imap_password"
cSettingImapSsl = "imap_ssl"
cSettingForwardAllowed = "mail_forward_allowed"

cSettingSmtpHost = "smtp_host"
cSettingSmtpPort = "smtp_port"
cSettingSmtpUser = "smtp_user"
cSettingSmtpPassword = "smtp_password"

cDefaultImapPort = 993
cDefaultSmtpPort = 587

# Seconds to wait for the mail server. Generous: a mailbox on the far side of a
# home connection is slower than an API, and a timeout here reads to the agent
# as "the mailbox is broken".
cTimeoutSeconds = 60

# How many messages one `mail.read` may return, whatever it asks for. An agent
# that pulls four hundred messages into its context spends its whole token
# ceiling on mail it was not going to act on.
cMaxMessages = 25

# How much of a body travels back. Enough to apply a rule, far short of a
# newsletter with its images inlined.
cMaxBodyCharacters = 4000

# Folders that are never deleted into or emptied, whatever an agent asks.
lProtectedFolders = ["INBOX"]

# One line of a LIST response: `(flags) delimiter name`. The delimiter is a
# quoted character or NIL; the name is everything after it, quoted or not, and
# is read as one piece rather than split on spaces so that `Deleted Items`
# survives.
cFolderLinePattern = re.compile(
  r'^\((?P<flags>[^)]*)\)\s+(?P<delimiter>NIL|"(?:[^"\\]|\\.)*")\s+(?P<name>.+)$',
  re.IGNORECASE
)

# `\` escapes the next character inside a quoted IMAP string.
cQuotedEscapePattern = re.compile(r"\\(.)")

# The `{12}` a server writes when the mailbox name travels as a literal.
cLiteralLengthPattern = re.compile(r"\{\d+\}\s*$")

# The SPECIAL-USE attribute that names the trash folder (RFC 6154). A server
# that sends it has told us which folder it is; everything else is a guess
# from a list of names in nine languages.
cTrashFlag = "\\trash"


class MailboxError(RuntimeError):
  """Raised when the mailbox is unconfigured, unreachable or refuses."""


def fReadSettings():
  """Return every stored setting as a dictionary of strings."""
  vConnection = db.fOpenAppDb()
  try:
    return {
      vRow["key"]: vRow["value"]
      for vRow in vConnection.execute("SELECT key, value FROM settings")
    }
  finally:
    vConnection.close()


def fIsConfigured(pSettings=None):
  """Return whether there is enough to reach a mailbox at all."""
  dSettings = pSettings if pSettings is not None else fReadSettings()
  return bool(dSettings.get(cSettingImapHost)
              and dSettings.get(cSettingImapUser)
              and dSettings.get(cSettingImapPassword))


def fListForwardAllowed(pSettings=None):
  """Return the addresses `mail.forward` may send to.

  Empty means forwarding is refused outright, which is the safe default: a
  feature that mails messages out of the account should not switch itself on
  because somebody filled in an IMAP host.
  """
  dSettings = pSettings if pSettings is not None else fReadSettings()
  vRaw = str(dSettings.get(cSettingForwardAllowed) or "")
  lAddresses = []
  for vPart in vRaw.replace(";", ",").replace("\n", ",").split(","):
    vAddress = vPart.strip().lower()
    if vAddress:
      lAddresses.append(vAddress)
  return lAddresses


def fIsForwardAllowed(pAddress, pSettings=None):
  """Return whether one address is on the list the user wrote.

  An entry of the form `@example.com` allows the whole domain, because "anyone
  at my company" is a thing people actually mean. Anything else has to match
  the address exactly.
  """
  vAddress = str(pAddress or "").strip().lower()
  if not vAddress or "@" not in vAddress:
    return False
  vDomain = "@" + vAddress.split("@")[-1]
  for vAllowed in fListForwardAllowed(pSettings):
    if vAllowed.startswith("@"):
      if vDomain == vAllowed:
        return True
    elif vAddress == vAllowed:
      return True
  return False


def fConnect(pSettings=None):
  """Open an IMAP connection and log in.

  The caller closes it. Raises MailboxError with what the server said, because
  "the mailbox failed" without the server's own words means reproducing the
  connection by hand to find out why.
  """
  dSettings = pSettings if pSettings is not None else fReadSettings()
  if not fIsConfigured(dSettings):
    raise MailboxError(
      "No mailbox is configured. Fill in the IMAP server under "
      "Settings -> Email."
    )

  vHost = dSettings[cSettingImapHost]
  try:
    vPort = int(dSettings.get(cSettingImapPort) or cDefaultImapPort)
  except (TypeError, ValueError):
    vPort = cDefaultImapPort
  vUseSsl = str(dSettings.get(cSettingImapSsl) or "1") not in ("0", "false", "no")

  try:
    if vUseSsl:
      vConnection = imaplib.IMAP4_SSL(vHost, vPort, timeout=cTimeoutSeconds,
                                      ssl_context=ssl.create_default_context())
    else:
      vConnection = imaplib.IMAP4(vHost, vPort, timeout=cTimeoutSeconds)
      vConnection.starttls(ssl_context=ssl.create_default_context())
    vConnection.login(dSettings[cSettingImapUser],
                      dSettings[cSettingImapPassword])
  except (imaplib.IMAP4.error, OSError, ssl.SSLError) as vError:
    raise MailboxError("Cannot reach the mailbox at %s:%d: %s"
                       % (vHost, vPort, vError))
  return vConnection


def fSelectFolder(pConnection, pFolder, pReadOnly=False):
  """Select one folder, raising with the server's answer when it refuses."""
  vFolder = str(pFolder or "INBOX").strip() or "INBOX"
  try:
    vStatus, lData = pConnection.select(_fQuoteFolder(vFolder),
                                        readonly=pReadOnly)
  except imaplib.IMAP4.error as vError:
    raise MailboxError("Cannot open folder %r: %s" % (vFolder, vError))
  if vStatus != "OK":
    raise MailboxError("Cannot open folder %r: %s"
                       % (vFolder, _fDescribe(lData)))
  return vFolder


# ----------------------------------------------- naming one message ----
#
# A message is named by its UID and the folder's UIDVALIDITY, never by its
# sequence number.
#
# The sequence number is the position of a message in a folder, and it changes
# the moment anything before it is expunged - by this code, by the phone in
# somebody's pocket, by the webmail open in another tab. It is also only valid
# inside the session that read it. `mail.read` handed those numbers to an
# agent, the agent used one in `mail.delete` minutes later, and that call
# opened a NEW connection: the number it sent meant whatever now sat in that
# position. Deleting the wrong message is not a failure anybody sees.
#
# The UID does not move. UIDVALIDITY travels with it because a UID only means
# anything inside the folder incarnation that issued it: a rebuilt mailbox
# starts numbering again, and the server says so by changing UIDVALIDITY. Told
# that the number it holds belonged to a folder that no longer exists, this
# refuses rather than acting on whatever inherited it.

cMessageIdSeparator = "."


def fBuildMessageId(pUidValidity, pUid):
  """Return the id an agent is given for one message."""
  return "%s%s%s" % (pUidValidity, cMessageIdSeparator, pUid)


def fParseMessageId(pMessageId):
  """Return (uidvalidity, uid) for an id this handed out, or raise.

  An id that is only a number is refused rather than guessed at. Those are the
  sequence numbers handed out before this existed, and the whole point is that
  a bare number cannot be resolved safely: acting on one is how the wrong
  message got deleted.
  """
  vRaw = str(pMessageId or "").strip()
  if not vRaw:
    raise MailboxError("No message id given.")

  vParts = vRaw.split(cMessageIdSeparator)
  if len(vParts) != 2 or not vParts[0].isdigit() or not vParts[1].isdigit():
    raise MailboxError(
      "%r is not a message id from mail.read. Read the folder again and use "
      "the id it gives you: ids are not sequence numbers and do not survive "
      "being guessed at." % (pMessageId,)
    )
  return vParts[0], vParts[1]


def fReadUidValidity(pConnection):
  """Return the selected folder's UIDVALIDITY as a string, or raise."""
  try:
    vStatus, lData = pConnection.response("UIDVALIDITY")
  except imaplib.IMAP4.error as vError:
    raise MailboxError("Cannot read UIDVALIDITY: %s" % (vError,))

  vValue = ""
  for vItem in lData or []:
    if isinstance(vItem, (bytes, bytearray)):
      vItem = bytes(vItem).decode("ascii", "replace")
    vValue = str(vItem or "").strip()
    if vValue:
      break
  if not vValue.isdigit():
    raise MailboxError(
      "The mail server did not say what this folder's UIDVALIDITY is, so "
      "there is no safe way to name a message in it."
    )
  return vValue


def fSelectFolderForMessage(pConnection, pFolder, pMessageId, pReadOnly=False):
  """Select the folder holding one message and return (folder, uid).

  Raises when the folder has been rebuilt since the id was handed out: the UID
  in the caller's hand then belongs to a numbering that no longer exists, and
  some other message has inherited it.
  """
  vExpectedValidity, vUid = fParseMessageId(pMessageId)
  vFolder = fSelectFolder(pConnection, pFolder, pReadOnly=pReadOnly)
  vValidity = fReadUidValidity(pConnection)
  if vValidity != vExpectedValidity:
    raise MailboxError(
      "Folder %r has been rebuilt since that message was read, so its ids no "
      "longer mean anything (UIDVALIDITY %s, not %s). Read the folder again."
      % (vFolder, vValidity, vExpectedValidity)
    )
  return vFolder, vUid


def fHasCapability(pConnection, pCapability):
  """Return whether the server announced one capability."""
  try:
    lCapabilities = pConnection.capabilities or ()
  except Exception:
    return False
  return str(pCapability).upper() in {str(v).upper() for v in lCapabilities}


def _fJoinListItem(pItem):
  """Return one item of a LIST response as a single line of text.

  imaplib hands back bytes for an ordinary line, and a tuple when the server
  sent the mailbox name as a literal: `(\\HasNoChildren) "/" {5}` and `Trash`
  arrive as two pieces. Joining them back - with the name quoted, so the
  parser below reads it as one token - is what lets a single parser read both
  shapes instead of the tuple falling through `str()` and becoming garbage.
  """
  if isinstance(pItem, (bytes, bytearray)):
    return bytes(pItem).decode("utf-8", "replace")

  if isinstance(pItem, tuple):
    lParts = []
    for vPart in pItem:
      if isinstance(vPart, (bytes, bytearray)):
        vPart = bytes(vPart).decode("utf-8", "replace")
      lParts.append(str(vPart))
    if len(lParts) < 2:
      return lParts[0] if lParts else ""
    # The `{5}` says how long the name is. The name itself is the next piece,
    # so the length prefix is dropped and the name put in its place.
    vHead = cLiteralLengthPattern.sub("", lParts[0])
    return '%s "%s"' % (vHead.rstrip(), lParts[1].replace('"', ""))

  return str(pItem)


def _fParseFolderLine(pLine):
  """Return one LIST line as {"flags", "delimiter", "name"}, or raise.

  A LIST response is `(flags) delimiter name`, and it is the name that varies:
  an atom (`Trash`), a quoted string (`"Deleted Items"`) or a literal. Reading
  it as "the last quoted part, or the last word" - which is what this used to
  do - returns the DELIMITER on every server that does not quote the name,
  because the delimiter is then the only quoted thing on the line.

  Measured: `(\\HasNoChildren) "/" Trash` came back as `/`. The trash folder
  was therefore never found, and `mail.delete` expunged the message outright
  instead of moving it - which is a message the user cannot get back.

  Raises MailboxError rather than skipping a line it cannot read: a folder
  list that silently loses entries is a mailbox that appears not to have a
  trash folder, and that is the failure this exists to prevent.
  """
  vLine = str(pLine or "").strip()
  dMatch = cFolderLinePattern.match(vLine)
  if dMatch is None:
    raise MailboxError(
      "Cannot read this folder listing from the mail server: %r" % (vLine,)
    )

  vName = dMatch.group("name").strip()
  if len(vName) >= 2 and vName.startswith('"') and vName.endswith('"'):
    # Quoted: the quotes come off and a backslash escapes the next character.
    vName = cQuotedEscapePattern.sub(r"\1", vName[1:-1])

  vDelimiter = dMatch.group("delimiter")
  if vDelimiter.upper() == "NIL":
    vDelimiter = ""
  else:
    vDelimiter = cQuotedEscapePattern.sub(r"\1", vDelimiter[1:-1])

  return {
    "flags": [vFlag.lower() for vFlag in dMatch.group("flags").split()],
    "delimiter": vDelimiter,
    "name": vName,
  }


def fListFoldersWithFlags(pConnection):
  """Return every folder as {"flags", "delimiter", "name"}, or raise.

  The flags are kept because one of them answers the question this module
  most needs answered: which folder is the trash.
  """
  vStatus, lData = pConnection.list()
  if vStatus != "OK":
    raise MailboxError(
      "The mail server refused to list the folders: %s" % (_fDescribe(lData),)
    )

  ldFolders = []
  for vItem in lData or []:
    dFolder = _fParseFolderLine(_fJoinListItem(vItem))
    if dFolder["name"]:
      ldFolders.append(dFolder)
  return ldFolders


def fListFolders(pConnection):
  """Return the folder names this account has."""
  return [dFolder["name"] for dFolder in fListFoldersWithFlags(pConnection)]


def fFindTrashFolder(pConnection):
  """Return the account's Trash folder, or an empty string when there is none.

  The SPECIAL-USE attribute first: a server that sends `\\Trash` has named the
  folder itself, in its own language and its own naming scheme, and no list of
  guesses beats being told. The names are tried after it, for the servers that
  do not send it.

  An empty string means the listing was read and holds no trash folder. A
  listing that cannot be read raises instead, because the caller turns "there
  is no trash" into a permanent deletion.
  """
  lCandidates = ["Trash", "INBOX.Trash", "Deleted Items", "Deleted Messages",
                 "INBOX.Deleted Items", "Papelera", "INBOX.Papelera",
                 "Corbeille", "Papierkorb"]
  ldExisting = fListFoldersWithFlags(pConnection)

  for dFolder in ldExisting:
    if cTrashFlag in dFolder["flags"]:
      return dFolder["name"]

  dLower = {dFolder["name"].lower(): dFolder["name"] for dFolder in ldExisting}
  for vCandidate in lCandidates:
    if vCandidate.lower() in dLower:
      return dLower[vCandidate.lower()]
  return ""


def fReadMessages(pFolder="INBOX", pOnlyUnread=True, pLimit=10, pSearch=""):
  """Return the newest messages of one folder, newest first.

  Marked as read is NOT done here. An agent that reads a mailbox and silently
  marks everything seen takes away the one signal the person was relying on.
  The folder is opened read-only, so nothing changes by looking.
  """
  vConnection = fConnect()
  try:
    fSelectFolder(vConnection, pFolder, pReadOnly=True)
    vValidity = fReadUidValidity(vConnection)

    lCriteria = ["UNSEEN"] if pOnlyUnread else ["ALL"]
    if pSearch:
      # Searched in the header and the body, which is what somebody means by
      # "messages about the invoice".
      lCriteria = lCriteria + ["TEXT", '"%s"' % (str(pSearch).replace('"', ""),)]

    # UID SEARCH, not SEARCH: what comes back has to stay meaningful after
    # this connection closes, and a sequence number does not.
    vStatus, lData = vConnection.uid("SEARCH", None, *lCriteria)
    if vStatus != "OK":
      raise MailboxError("The mailbox refused the search: %s" % (_fDescribe(lData),))

    lUids = (lData[0] or b"").split()
    vLimit = max(1, min(int(pLimit or 10), cMaxMessages))
    lUids = lUids[-vLimit:][::-1]           # newest first

    ldMessages = []
    for vUid in lUids:
      vStatus, lFetched = vConnection.uid("FETCH", vUid, "(BODY.PEEK[])")
      if vStatus != "OK" or not lFetched or not isinstance(lFetched[0], tuple):
        continue
      dMessage = _fDescribeMessage(
        fBuildMessageId(vValidity, vUid.decode("ascii", "replace")),
        lFetched[0][1]
      )
      ldMessages.append(dMessage)
    return ldMessages
  finally:
    _fClose(vConnection)


def fDeleteMessage(pMessageId, pFolder="INBOX"):
  """Move one message to Trash, or expunge it when there is no Trash folder.

  The trash folder is looked up before anything is flagged, and a lookup that
  FAILS stops the deletion rather than falling through to the expunge below.
  The difference matters more than it reads: "this account has no trash" and
  "the folder list could not be read" used to arrive here as the same empty
  string, so one unparsed line from the mail server turned every `mail.delete`
  into a permanent one.
  """
  vConnection = fConnect()
  try:
    vFolder, vUid = fSelectFolderForMessage(vConnection, pFolder, pMessageId)
    try:
      vTrash = fFindTrashFolder(vConnection)
    except MailboxError as vError:
      raise MailboxError(
        "Not deleting message %s: the mail server's folder list could not be "
        "read, so there is no way to tell whether this account has a trash "
        "folder. %s" % (pMessageId, vError)
      )

    if vTrash and vTrash.lower() != vFolder.lower():
      vHow = _fMoveByUid(vConnection, vUid, vTrash)
      return {"moved_to": vTrash, "expunged": False, "how": vHow}

    # No Trash folder: the only honest thing left is to say that this one is
    # gone for good.
    vStatus, lData = vConnection.uid("STORE", vUid, "+FLAGS", "\\Deleted")
    if vStatus != "OK":
      raise MailboxError("Cannot delete message %s: %s"
                         % (pMessageId, _fDescribe(lData)))

    # UID EXPUNGE where the server has it: a bare EXPUNGE purges every message
    # in the folder carrying \Deleted, and some of those may be another
    # client's, flagged and not yet expunged. Without UIDPLUS the message is
    # left flagged instead, which every client shows as deleted and none of
    # them shows as somebody else's mail disappearing.
    if fHasCapability(vConnection, "UIDPLUS"):
      vStatus, lData = vConnection.uid("EXPUNGE", vUid)
      if vStatus == "OK":
        return {"moved_to": "", "expunged": True, "how": "uid-expunge"}
    return {"moved_to": "", "expunged": False, "how": "flagged"}
  finally:
    _fClose(vConnection)


def fMoveMessage(pMessageId, pTargetFolder, pFolder="INBOX"):
  """Move one message from one folder to another."""
  vTarget = str(pTargetFolder or "").strip()
  if not vTarget:
    raise MailboxError("No destination folder given.")

  vConnection = fConnect()
  try:
    vFolder, vUid = fSelectFolderForMessage(vConnection, pFolder, pMessageId)
    lFolders = fListFolders(vConnection)
    dLower = {vName.lower(): vName for vName in lFolders}
    if vTarget.lower() not in dLower:
      raise MailboxError(
        "There is no folder called %r. This account has: %s"
        % (vTarget, ", ".join(lFolders) or "none")
      )
    vTarget = dLower[vTarget.lower()]

    # Listing the folders re-selects nothing, but LIST can change the selected
    # folder on some servers, so the folder is selected again by name before
    # the UID is used against it.
    fSelectFolder(vConnection, vFolder)
    vHow = _fMoveByUid(vConnection, vUid, vTarget)
    return {"moved_to": vTarget, "how": vHow}
  finally:
    _fClose(vConnection)


def fForwardMessage(pMessageId, pTo, pNote="", pFolder="INBOX"):
  """Forward one message to an address the user allowed.

  The allow list is checked here rather than in the tool: this is the process
  that holds the password and opens the connection, and it is the only place a
  check cannot be talked out of by something written in an email.
  """
  dSettings = fReadSettings()
  vTo = str(pTo or "").strip()
  if not fIsForwardAllowed(vTo, dSettings):
    lAllowed = fListForwardAllowed(dSettings)
    if not lAllowed:
      raise MailboxError(
        "Forwarding is switched off: no allowed recipients are configured. "
        "Add them under Settings -> Email."
      )
    raise MailboxError(
      "%s is not an allowed recipient. Allowed: %s"
      % (vTo, ", ".join(lAllowed))
    )

  if not dSettings.get(cSettingSmtpHost):
    raise MailboxError(
      "No outgoing mail server is configured. Fill in SMTP under "
      "Settings -> Email."
    )

  vConnection = fConnect(dSettings)
  try:
    vFolder, vUid = fSelectFolderForMessage(
      vConnection, pFolder, pMessageId, pReadOnly=True)
    vStatus, lFetched = vConnection.uid("FETCH", vUid, "(BODY.PEEK[])")
    if vStatus != "OK" or not lFetched or not isinstance(lFetched[0], tuple):
      raise MailboxError("There is no message %s in %s" % (pMessageId, vFolder))
    vOriginalBytes = lFetched[0][1]
  finally:
    _fClose(vConnection)

  vOriginal = email.message_from_bytes(vOriginalBytes)
  vFrom = (dSettings.get(cSettingSmtpUser)
           or dSettings.get(cSettingImapUser) or "")

  vForward = email.message.EmailMessage()
  vForward["From"] = vFrom
  vForward["To"] = vTo
  vForward["Subject"] = "Fwd: %s" % (_fDecodeHeader(vOriginal.get("Subject", "")),)
  vForward["Date"] = email.utils.formatdate(localtime=True)
  vForward["Message-ID"] = email.utils.make_msgid()
  vForward.set_content(str(pNote or "Forwarded by an agent."))
  # Attached whole, rather than quoted into the body: the recipient gets the
  # real message, with its own headers, and nothing is lost in the retelling.
  vForward.add_attachment(vOriginalBytes, maintype="message", subtype="rfc822")

  _fSend(dSettings, vFrom, vTo, vForward)
  return {"forwarded_to": vTo, "subject": vForward["Subject"]}


# ------------------------------------------------------------- internals ----

def _fQuoteFolder(pFolder):
  """Quote a folder name, since plenty of them contain spaces."""
  return '"%s"' % (str(pFolder).replace('"', ""),)


def _fDescribe(pData):
  """Turn whatever imaplib handed back into one readable line."""
  if not pData:
    return "no reason given"
  vFirst = pData[0]
  if isinstance(vFirst, bytes):
    return vFirst.decode("utf-8", "replace")
  return str(vFirst)


def _fClose(pConnection):
  """Close and log out, never failing on the way out."""
  try:
    pConnection.close()
  except Exception:
    pass
  try:
    pConnection.logout()
  except Exception:
    pass


def _fMoveByUid(pConnection, pUid, pTargetFolder):
  """Move one message to another folder. Returns how it was done.

  Three ways, best first, and which one is available is the server's answer
  rather than a guess:

    MOVE      RFC 6851. One command, atomic, nothing left flagged behind.
    UIDPLUS   COPY, flag, then UID EXPUNGE - which removes THAT message and
              nothing else.
    neither   COPY and flag, and stop there. A plain EXPUNGE would remove
              every message in the folder that carries \\Deleted, including
              ones another client flagged and has not expunged yet, and
              purging somebody else's mail to move one of ours is not a
              trade this gets to make on its own. The message is copied and
              marked; nearly every client hides it, and the next expunge by
              whoever owns that decision clears it.
  """
  if fHasCapability(pConnection, "MOVE"):
    vStatus, lData = pConnection.uid("MOVE", pUid, _fQuoteFolder(pTargetFolder))
    if vStatus != "OK":
      raise MailboxError("Cannot move message to %s: %s"
                         % (pTargetFolder, _fDescribe(lData)))
    return "move"

  vStatus, lData = pConnection.uid("COPY", pUid, _fQuoteFolder(pTargetFolder))
  if vStatus != "OK":
    raise MailboxError("Cannot copy message to %s: %s"
                       % (pTargetFolder, _fDescribe(lData)))

  vStatus, lData = pConnection.uid("STORE", pUid, "+FLAGS", "\\Deleted")
  if vStatus != "OK":
    raise MailboxError("Copied the message to %s but could not remove the "
                       "original: %s" % (pTargetFolder, _fDescribe(lData)))

  if fHasCapability(pConnection, "UIDPLUS"):
    vStatus, lData = pConnection.uid("EXPUNGE", pUid)
    if vStatus == "OK":
      return "uid-expunge"
  return "copy-and-flag"


def _fDecodeHeader(pValue):
  """Decode a header that may be RFC 2047 encoded, never raising."""
  try:
    lParts = email.header.decode_header(pValue or "")
  except Exception:
    return str(pValue or "")
  lText = []
  for vPart, vCharset in lParts:
    if isinstance(vPart, bytes):
      lText.append(vPart.decode(vCharset or "utf-8", "replace"))
    else:
      lText.append(vPart)
  return "".join(lText)


def _fExtractBody(pMessage):
  """Return the plain text of a message, cut to a readable length.

  text/plain is preferred and HTML is taken only when there is nothing else,
  tags and all: stripping HTML properly is a library, and an agent reading the
  markup still finds the sentence it was looking for.
  """
  vText = ""
  if pMessage.is_multipart():
    for vPart in pMessage.walk():
      if vPart.get_content_maintype() == "multipart":
        continue
      if vPart.get_content_disposition() == "attachment":
        continue
      vType = vPart.get_content_type()
      if vType == "text/plain":
        vText = _fDecodePayload(vPart)
        break
      if vType == "text/html" and not vText:
        vText = _fDecodePayload(vPart)
  else:
    vText = _fDecodePayload(pMessage)

  vText = vText.strip()
  if len(vText) > cMaxBodyCharacters:
    vText = vText[:cMaxBodyCharacters] + "\n[... cut, the message is longer]"
  return vText


def _fDecodePayload(pPart):
  """Decode one part's payload into text, never raising."""
  try:
    vPayload = pPart.get_payload(decode=True)
  except Exception:
    return ""
  if vPayload is None:
    return ""
  vCharset = pPart.get_content_charset() or "utf-8"
  try:
    return vPayload.decode(vCharset, "replace")
  except LookupError:
    return vPayload.decode("utf-8", "replace")


def _fDescribeMessage(pId, pRawBytes):
  """Turn one raw message into what an agent is told about it."""
  vMessage = email.message_from_bytes(pRawBytes)
  lAttachments = []
  if vMessage.is_multipart():
    for vPart in vMessage.walk():
      if vPart.get_content_disposition() == "attachment":
        lAttachments.append({
          "name": _fDecodeHeader(vPart.get_filename() or "unnamed"),
          "type": vPart.get_content_type(),
        })
  return {
    "id": pId,
    "from": _fDecodeHeader(vMessage.get("From", "")),
    "to": _fDecodeHeader(vMessage.get("To", "")),
    "subject": _fDecodeHeader(vMessage.get("Subject", "")),
    "date": vMessage.get("Date", ""),
    "body": _fExtractBody(vMessage),
    # Named, never opened. What an attachment claims to be is a fact about the
    # message; what is inside it is not something to hand a language model.
    "attachments": lAttachments,
  }


def _fSend(pSettings, pFrom, pTo, pMessage):
  """Send one built message over the configured SMTP server."""
  vHost = pSettings.get(cSettingSmtpHost)
  try:
    vPort = int(pSettings.get(cSettingSmtpPort) or cDefaultSmtpPort)
  except (TypeError, ValueError):
    vPort = cDefaultSmtpPort

  try:
    if vPort == 465:
      vServer = smtplib.SMTP_SSL(vHost, vPort, timeout=cTimeoutSeconds,
                                 context=ssl.create_default_context())
    else:
      vServer = smtplib.SMTP(vHost, vPort, timeout=cTimeoutSeconds)
      vServer.starttls(context=ssl.create_default_context())
    try:
      if pSettings.get(cSettingSmtpUser):
        vServer.login(pSettings[cSettingSmtpUser],
                      pSettings.get(cSettingSmtpPassword) or "")
      vServer.send_message(pMessage, from_addr=pFrom, to_addrs=[pTo])
    finally:
      try:
        vServer.quit()
      except Exception:
        pass
  except (smtplib.SMTPException, OSError, ssl.SSLError) as vError:
    raise MailboxError("Cannot send through %s:%d: %s" % (vHost, vPort, vError))
