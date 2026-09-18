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


def fListFolders(pConnection):
  """Return the folder names this account has."""
  vStatus, lData = pConnection.list()
  if vStatus != "OK":
    return []
  lFolders = []
  for vLine in lData or []:
    if isinstance(vLine, bytes):
      vLine = vLine.decode("utf-8", "replace")
    # `(\HasNoChildren) "/" "INBOX.Sent"` - the name is the last quoted part,
    # or the last word when the server does not quote it.
    if '"' in vLine:
      lFolders.append(vLine.split('"')[-2] if vLine.rstrip().endswith('"')
                      else vLine.rsplit('"', 2)[-2])
    else:
      lFolders.append(vLine.split()[-1])
  return [vFolder for vFolder in lFolders if vFolder]


def fFindTrashFolder(pConnection):
  """Return the account's Trash folder, or an empty string when there is none.

  Names differ by server and by language, so the usual ones are tried by name
  rather than guessed from a flag most servers do not send.
  """
  lCandidates = ["Trash", "INBOX.Trash", "Deleted Items", "Deleted Messages",
                 "INBOX.Deleted Items", "Papelera", "INBOX.Papelera",
                 "Corbeille", "Papierkorb"]
  lExisting = fListFolders(pConnection)
  sLower = {vFolder.lower(): vFolder for vFolder in lExisting}
  for vCandidate in lCandidates:
    if vCandidate.lower() in sLower:
      return sLower[vCandidate.lower()]
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

    lCriteria = ["UNSEEN"] if pOnlyUnread else ["ALL"]
    if pSearch:
      # Searched in the header and the body, which is what somebody means by
      # "messages about the invoice".
      lCriteria = lCriteria + ["TEXT", '"%s"' % (str(pSearch).replace('"', ""),)]

    vStatus, lData = vConnection.search(None, *lCriteria)
    if vStatus != "OK":
      raise MailboxError("The mailbox refused the search: %s" % (_fDescribe(lData),))

    lIds = (lData[0] or b"").split()
    vLimit = max(1, min(int(pLimit or 10), cMaxMessages))
    lIds = lIds[-vLimit:][::-1]           # newest first

    ldMessages = []
    for vId in lIds:
      vStatus, lFetched = vConnection.fetch(vId, "(BODY.PEEK[])")
      if vStatus != "OK" or not lFetched or not isinstance(lFetched[0], tuple):
        continue
      dMessage = _fDescribeMessage(vId.decode("ascii", "replace"), lFetched[0][1])
      ldMessages.append(dMessage)
    return ldMessages
  finally:
    _fClose(vConnection)


def fDeleteMessage(pMessageId, pFolder="INBOX"):
  """Move one message to Trash, or expunge it when there is no Trash folder."""
  vConnection = fConnect()
  try:
    vFolder = fSelectFolder(vConnection, pFolder)
    vTrash = fFindTrashFolder(vConnection)

    if vTrash and vTrash.lower() != vFolder.lower():
      _fCopyAndFlag(vConnection, pMessageId, vTrash)
      vConnection.expunge()
      return {"moved_to": vTrash, "expunged": False}

    # No Trash folder: the only honest thing left is to say that this one is
    # gone for good.
    vStatus, lData = vConnection.store(str(pMessageId), "+FLAGS", "\\Deleted")
    if vStatus != "OK":
      raise MailboxError("Cannot delete message %s: %s"
                         % (pMessageId, _fDescribe(lData)))
    vConnection.expunge()
    return {"moved_to": "", "expunged": True}
  finally:
    _fClose(vConnection)


def fMoveMessage(pMessageId, pTargetFolder, pFolder="INBOX"):
  """Move one message from one folder to another."""
  vTarget = str(pTargetFolder or "").strip()
  if not vTarget:
    raise MailboxError("No destination folder given.")

  vConnection = fConnect()
  try:
    fSelectFolder(vConnection, pFolder)
    lFolders = fListFolders(vConnection)
    sLower = {vFolder.lower(): vFolder for vFolder in lFolders}
    if vTarget.lower() not in sLower:
      raise MailboxError(
        "There is no folder called %r. This account has: %s"
        % (vTarget, ", ".join(lFolders) or "none")
      )
    vTarget = sLower[vTarget.lower()]

    _fCopyAndFlag(vConnection, pMessageId, vTarget)
    vConnection.expunge()
    return {"moved_to": vTarget}
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
    fSelectFolder(vConnection, pFolder, pReadOnly=True)
    vStatus, lFetched = vConnection.fetch(str(pMessageId), "(BODY.PEEK[])")
    if vStatus != "OK" or not lFetched or not isinstance(lFetched[0], tuple):
      raise MailboxError("There is no message %s in %s" % (pMessageId, pFolder))
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


def _fCopyAndFlag(pConnection, pMessageId, pTargetFolder):
  """Copy one message somewhere and mark the original deleted."""
  vStatus, lData = pConnection.copy(str(pMessageId),
                                    _fQuoteFolder(pTargetFolder))
  if vStatus != "OK":
    raise MailboxError("Cannot copy message %s to %s: %s"
                       % (pMessageId, pTargetFolder, _fDescribe(lData)))
  vStatus, lData = pConnection.store(str(pMessageId), "+FLAGS", "\\Deleted")
  if vStatus != "OK":
    raise MailboxError("Copied message %s to %s but could not remove the "
                       "original: %s"
                       % (pMessageId, pTargetFolder, _fDescribe(lData)))


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
