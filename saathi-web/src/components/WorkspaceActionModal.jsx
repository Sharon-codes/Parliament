import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarDays, CheckCircle2, FileText, LoaderCircle, Mail, UserRound, X } from "lucide-react";

import { apiFetch } from "../lib/api";

const ACTION_META = {
  email: {
    title: "Send Email",
    description: "Look up the person from Google Contacts, confirm the email, then send.",
    icon: Mail,
  },
  meeting: {
    title: "Schedule Meeting",
    description: "Resolve the contact first, then create a Google Meet event with the right attendee.",
    icon: CalendarDays,
  },
  doc: {
    title: "Create Google Doc",
    description: "Create the document directly without sending the request through the chat model.",
    icon: FileText,
  },
};

function toLocalInputValue(date) {
  const value = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return value.toISOString().slice(0, 16);
}

function buildDefaultMeetingRange() {
  const start = new Date();
  start.setMinutes(start.getMinutes() + 30, 0, 0);
  const end = new Date(start.getTime() + 30 * 60000);
  return { start: toLocalInputValue(start), end: toLocalInputValue(end) };
}

function stripCommand(type, prompt) {
  const text = (prompt || "").trim();
  if (!text) return "";
  if (type === "email") return text.replace(/^(mail|email|send email|compose email)\s*/i, "").trim();
  if (type === "meeting") return text.replace(/^(meeting|schedule meeting|book meeting|create meeting)\s*/i, "").trim();
  if (type === "doc") return text.replace(/^(doc|document|create doc|create google doc|make google doc)\s*/i, "").trim();
  return text;
}

function normalizeContactValue(value) {
  return (value || "").trim().toLowerCase();
}

function parsePromptSeed(type, prompt) {
  const seed = stripCommand(type, prompt);
  if (!seed) return { contactQuery: "", email: "", content: "" };
  if (!["email", "meeting"].includes(type)) return { contactQuery: "", email: "", content: seed };

  const patterns = [
    /^(?:to|for|with)\s+([^:\n]+?)\s*[:,-]\s*([\s\S]+)$/i,
    /^(?:to|for|with)\s+([^:\n]+?)\s*\n+([\s\S]+)$/i,
    /^([^:@\n]{2,80})\s*:\s*([\s\S]+)$/i,
  ];

  let recipient = "";
  let content = seed;
  for (const pattern of patterns) {
    const match = seed.match(pattern);
    if (match) {
      recipient = match[1].trim();
      content = match[2].trim();
      break;
    }
  }

  if (!recipient) {
    const recipientOnlyMatch = seed.match(/^(?:to|for|with)\s+([^:\n]+)$/i);
    if (recipientOnlyMatch) {
      recipient = recipientOnlyMatch[1].trim();
      content = "";
    }
  }

  if (!recipient) {
    const recipientColonOnlyMatch = seed.match(/^(?:to|for|with)\s+([^:\n]+?)\s*:\s*$/i);
    if (recipientColonOnlyMatch) {
      recipient = recipientColonOnlyMatch[1].trim();
      content = "";
    }
  }

  if (!recipient) return { contactQuery: "", email: "", content: seed };
  if (recipient.includes("@")) return { contactQuery: "", email: recipient, content };
  return { contactQuery: recipient, email: "", content };
}

function dedupeContacts(contacts) {
  const seen = new Set();
  return (contacts || []).filter((contact) => {
    const key = normalizeContactValue(contact?.email);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function WorkspaceActionModal({
  open,
  type,
  session,
  initialPrompt,
  currentFile,
  onClose,
  onSuccess,
}) {
  const meta = ACTION_META[type];
  const Icon = meta?.icon || Mail;
  const defaultMeetingRange = useMemo(() => buildDefaultMeetingRange(), [open, type]);
  const [isNarrow, setIsNarrow] = useState(() => (typeof window !== "undefined" ? window.innerWidth <= 720 : false));
  const [personName, setPersonName] = useState("");
  const [email, setEmail] = useState("");
  const [contacts, setContacts] = useState([]);
  const [bestMatch, setBestMatch] = useState(null);
  const [contactLoading, setContactLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [meetingTitle, setMeetingTitle] = useState("Quick Sync");
  const [meetingDescription, setMeetingDescription] = useState("");
  const [meetingStart, setMeetingStart] = useState(defaultMeetingRange.start);
  const [meetingEnd, setMeetingEnd] = useState(defaultMeetingRange.end);
  const [contactHint, setContactHint] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [docPrompt, setDocPrompt] = useState("");
  const [docContent, setDocContent] = useState("");
  const [generateDoc, setGenerateDoc] = useState(false);
  const [recipientLocked, setRecipientLocked] = useState(false);
  const [selectedContactName, setSelectedContactName] = useState("");
  const [selectedRecipientKey, setSelectedRecipientKey] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const handleResize = () => setIsNarrow(window.innerWidth <= 720);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!open) return;

    const parsedSeed = parsePromptSeed(type, initialPrompt);
    const meetingRange = buildDefaultMeetingRange();

    setPersonName(parsedSeed.contactQuery);
    setEmail(parsedSeed.email);
    setContacts([]);
    setBestMatch(null);
    setContactLoading(false);
    setSubmitting(false);
    setError("");
    setSubject(type === "email" ? "Quick note" : "");
    setBody(type === "email" ? parsedSeed.content : "");
    setMeetingTitle(parsedSeed.contactQuery ? `Meeting with ${parsedSeed.contactQuery}` : parsedSeed.content ? "Meeting" : "Quick Sync");
    setMeetingDescription(type === "meeting" ? parsedSeed.content : "");
    setMeetingStart(meetingRange.start);
    setMeetingEnd(meetingRange.end);
    setContactHint("");
    setDocTitle(currentFile?.name ? `Notes - ${currentFile.name}` : "New Google Doc");
    setDocPrompt(type === "doc" ? parsedSeed.content : "");
    setDocContent(currentFile?.content || "");
    setGenerateDoc(type === "doc" && !currentFile?.content && Boolean(parsedSeed.content));
    setRecipientLocked(Boolean(parsedSeed.email));
    setSelectedContactName(parsedSeed.contactQuery);
    setSelectedRecipientKey(normalizeContactValue(parsedSeed.email));
  }, [open, type, initialPrompt, currentFile]);

  useEffect(() => {
    if (!open || !["email", "meeting"].includes(type)) return;

    const query = personName.trim();
    if (query.length < 2) {
      setContacts([]);
      setBestMatch(null);
      setContactHint("");
      if (!recipientLocked && query.includes("@")) {
        setEmail((current) => current.trim() || query);
      }
      return;
    }

    const timer = window.setTimeout(async () => {
      setContactLoading(true);
      setError("");
      try {
        const result = await apiFetch(`/api/workspace/contacts/search?query=${encodeURIComponent(query)}`, { session });
        const nextContacts = dedupeContacts(result.contacts || []);
        const nextBestMatch = result.bestMatch || nextContacts[0] || null;

        setContacts(nextContacts);
        setBestMatch(nextBestMatch);
        setContactHint(nextContacts.length ? "" : "No saved Google Contact matched. You can still type the email manually.");

        if (!recipientLocked && nextBestMatch?.email) {
          setEmail((current) => current.trim() || nextBestMatch.email);
        }

        if (!recipientLocked && !nextBestMatch?.email && query.includes("@")) {
          setEmail((current) => current.trim() || query);
        }
      } catch (err) {
        setContactHint("Contact search is unavailable right now. You can still type the email manually.");
      } finally {
        setContactLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(timer);
  }, [open, type, personName, session, recipientLocked]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      if (type === "email") {
        if (!email.trim()) throw new Error("Choose a contact or type the recipient email before sending.");
        const result = await apiFetch("/api/workspace/emails/send", {
          session,
          method: "POST",
          body: { to: email.trim(), subject, body },
        });
        onSuccess?.({ assistantText: `Email sent to ${email.trim()}.`, payload: result });
      }

      if (type === "meeting") {
        if (!email.trim()) throw new Error("Choose a contact or type the attendee email before scheduling.");
        const result = await apiFetch("/api/workspace/calendar/events", {
          session,
          method: "POST",
          body: {
            title: meetingTitle,
            description: meetingDescription,
            start: meetingStart,
            end: meetingEnd,
            attendees: email.trim() ? [email.trim()] : [],
            generate_meet: true,
          },
        });
        const meetLink = result?.event?.hangoutLink;
        onSuccess?.({
          assistantText: meetLink ? `Meeting scheduled with ${email.trim()}. Meet link: ${meetLink}` : `Meeting scheduled with ${email.trim()}.`,
          payload: result,
        });
      }

      if (type === "doc") {
        const result = await apiFetch("/api/workspace/docs", {
          session,
          method: "POST",
          body: {
            title: docTitle,
            content: docContent,
            prompt: docPrompt,
            generate: generateDoc,
          },
        });
        onSuccess?.({ assistantText: `Google Doc created: ${result?.document?.url || docTitle}`, payload: result });
      }
    } catch (err) {
      setError(err.message || "The action could not be completed.");
    } finally {
      setSubmitting(false);
    }
  }

  function selectContact(contact) {
    const nextEmail = contact.email || "";
    setPersonName(contact.name || "");
    setEmail(nextEmail);
    setBestMatch(contact);
    setContactHint("");
    setRecipientLocked(Boolean(nextEmail));
    setSelectedContactName(contact.name || "");
    setSelectedRecipientKey(normalizeContactValue(nextEmail));
  }

  function handlePersonNameChange(event) {
    const nextValue = event.target.value;
    setPersonName(nextValue);

    if (recipientLocked && normalizeContactValue(nextValue) !== normalizeContactValue(selectedContactName)) {
      setRecipientLocked(false);
      setSelectedContactName("");
      setSelectedRecipientKey("");
    }

    if (!nextValue.trim()) setEmail("");
  }

  function handleEmailChange(event) {
    const nextValue = event.target.value;
    const normalizedEmail = normalizeContactValue(nextValue);
    setEmail(nextValue);
    setRecipientLocked(Boolean(normalizedEmail));
    setSelectedRecipientKey(normalizedEmail);
    if (selectedContactName && normalizedEmail !== normalizeContactValue(bestMatch?.email)) {
      setSelectedContactName("");
    }
  }

  const showContactSection = type === "email" || type === "meeting";
  const alternateContacts = dedupeContacts(contacts).filter(
    (contact) => normalizeContactValue(contact.email) !== normalizeContactValue(bestMatch?.email),
  );
  const suggestionDiffers =
    !recipientLocked &&
    bestMatch?.email &&
    email &&
    normalizeContactValue(bestMatch.email) !== normalizeContactValue(email);
  const bestMatchSelected = normalizeContactValue(bestMatch?.email) && normalizeContactValue(bestMatch?.email) === selectedRecipientKey;
  const lockedRecipientMessage =
    recipientLocked && email ? `Recipient locked to ${email}. Edit the person or email field if you want to switch.` : "";

  return (
    <AnimatePresence>
      {open && meta && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(28, 25, 23, 0.38)",
            backdropFilter: "blur(12px)",
            zIndex: 200000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: isNarrow ? "12px" : "24px",
          }}
        >
          <motion.form
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 18, scale: 0.98 }}
            onSubmit={handleSubmit}
            style={{
              width: "min(720px, 100%)",
              maxHeight: "calc(100vh - 24px)",
              background: "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(245,245,244,0.97))",
              borderRadius: isNarrow ? "22px" : "28px",
              border: "1px solid rgba(231,229,228,0.95)",
              boxShadow: "0 30px 80px rgba(28,25,23,0.18)",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div style={{ padding: isNarrow ? "18px 18px 14px" : "24px 28px 16px", borderBottom: "1px solid #e7e5e4" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <div
                  style={{
                    width: isNarrow ? "46px" : "52px",
                    height: isNarrow ? "46px" : "52px",
                    borderRadius: "16px",
                    background: "#1c1917",
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={isNarrow ? 20 : 24} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3 className="serif" style={{ fontSize: isNarrow ? "1.35rem" : "1.7rem", margin: 0 }}>{meta.title}</h3>
                  <p style={{ margin: "6px 0 0", color: "#57534e", lineHeight: 1.5, fontSize: isNarrow ? "0.92rem" : "1rem" }}>
                    {meta.description}
                  </p>
                </div>
                <button type="button" onClick={onClose} style={{ background: "none", border: "none", color: "#78716c", cursor: "pointer" }}>
                  <X size={22} />
                </button>
              </div>
            </div>

            <div style={{ padding: isNarrow ? "18px" : "24px 28px", display: "grid", gap: "18px", overflowY: "auto" }}>
              {showContactSection && (
                <>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Person
                    </span>
                    <div style={{ position: "relative" }}>
                      <UserRound size={18} style={{ position: "absolute", left: "16px", top: "50%", transform: "translateY(-50%)", color: "#a8a29e" }} />
                      <input
                        value={personName}
                        onChange={handlePersonNameChange}
                        placeholder="Type a name from Google Contacts"
                        style={{
                          width: "100%",
                          borderRadius: "18px",
                          border: "1px solid #d6d3d1",
                          background: "white",
                          padding: "16px 18px 16px 46px",
                          fontSize: "1rem",
                          outline: "none",
                        }}
                      />
                      {contactLoading && <LoaderCircle size={18} className="animate-spin" style={{ position: "absolute", right: "16px", top: "50%", transform: "translateY(-50%)", color: "#78716c" }} />}
                    </div>
                  </label>

                  {bestMatch && (
                    <div style={{ borderRadius: "20px", background: bestMatchSelected ? "#ecfdf5" : "#fafaf9", border: `1px solid ${bestMatchSelected ? "#86efac" : "#e7e5e4"}`, padding: "16px 18px" }}>
                      <div style={{ display: "flex", alignItems: isNarrow ? "stretch" : "center", justifyContent: "space-between", gap: "12px", flexDirection: isNarrow ? "column" : "row" }}>
                        <div>
                          <div style={{ fontWeight: 700, color: "#1c1917" }}>{bestMatch.name}</div>
                          <div style={{ color: "#57534e", fontSize: "0.95rem", overflowWrap: "anywhere" }}>{bestMatch.email}</div>
                          {bestMatch.organization && <div style={{ color: "#78716c", fontSize: "0.82rem", marginTop: "4px" }}>{bestMatch.organization}</div>}
                        </div>
                        <button type="button" onClick={() => selectContact(bestMatch)} className="pill-btn" style={{ minWidth: isNarrow ? "100%" : "140px", justifyContent: "center" }}>
                          <CheckCircle2 size={18} />
                          <span>{bestMatchSelected ? "Selected" : "Use This"}</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {alternateContacts.length > 0 && (
                    <div style={{ display: "grid", gap: "10px", maxHeight: isNarrow ? "180px" : "220px", overflowY: "auto" }}>
                      {alternateContacts.slice(0, 4).map((contact) => {
                        const contactSelected = normalizeContactValue(contact.email) === selectedRecipientKey;
                        return (
                          <button
                            key={`${contact.email}-${contact.name}`}
                            type="button"
                            onClick={() => selectContact(contact)}
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              gap: "12px",
                              alignItems: "center",
                              padding: "12px 16px",
                              borderRadius: "16px",
                              border: `1px solid ${contactSelected ? "#86efac" : "#e7e5e4"}`,
                              background: contactSelected ? "#ecfdf5" : "white",
                              cursor: "pointer",
                              textAlign: "left",
                            }}
                          >
                            <span style={{ minWidth: 0 }}>
                              <strong style={{ display: "block" }}>{contact.name}</strong>
                              <span style={{ display: "block", fontSize: "0.88rem", color: "#57534e", marginTop: "4px", overflowWrap: "anywhere" }}>{contact.email}</span>
                            </span>
                            <span style={{ color: "#78716c", fontSize: "0.82rem", flexShrink: 0 }}>{contactSelected ? "Selected" : "Use"}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}

                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Email
                    </span>
                    <input
                      value={email}
                      onChange={handleEmailChange}
                      placeholder="Confirm or correct the email address"
                      style={{
                        width: "100%",
                        borderRadius: "18px",
                        border: "1px solid #d6d3d1",
                        background: "white",
                        padding: "16px 18px",
                        fontSize: "1rem",
                        outline: "none",
                      }}
                    />
                  </label>

                  {lockedRecipientMessage && (
                    <div style={{ borderRadius: "16px", background: "#ecfdf5", color: "#166534", border: "1px solid #86efac", padding: "12px 14px" }}>
                      {lockedRecipientMessage}
                    </div>
                  )}

                  {suggestionDiffers && (
                    <div style={{ borderRadius: "16px", background: "#fff7ed", color: "#9a3412", border: "1px solid #fdba74", padding: "12px 14px" }}>
                      Closest Google Contact match: <strong>{bestMatch.name}</strong> at <strong>{bestMatch.email}</strong>
                    </div>
                  )}

                  {contactHint && (
                    <div style={{ borderRadius: "16px", background: "#eff6ff", color: "#1d4ed8", border: "1px solid #93c5fd", padding: "12px 14px" }}>
                      {contactHint}
                    </div>
                  )}
                </>
              )}
              {type === "email" && (
                <>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Subject
                    </span>
                    <input value={subject} onChange={(event) => setSubject(event.target.value)} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none" }} />
                  </label>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Message
                    </span>
                    <textarea
                      value={body}
                      onChange={(event) => setBody(event.target.value)}
                      rows={isNarrow ? 5 : 7}
                      style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none", resize: "vertical", minHeight: isNarrow ? "140px" : "180px", maxHeight: "280px" }}
                    />
                  </label>
                </>
              )}

              {type === "meeting" && (
                <>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Meeting Title
                    </span>
                    <input value={meetingTitle} onChange={(event) => setMeetingTitle(event.target.value)} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none" }} />
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr", gap: "14px" }}>
                    <label style={{ display: "grid", gap: "8px" }}>
                      <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                        Start
                      </span>
                      <input type="datetime-local" value={meetingStart} onChange={(event) => setMeetingStart(event.target.value)} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none" }} />
                    </label>
                    <label style={{ display: "grid", gap: "8px" }}>
                      <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                        End
                      </span>
                      <input type="datetime-local" value={meetingEnd} onChange={(event) => setMeetingEnd(event.target.value)} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none" }} />
                    </label>
                  </div>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Notes
                    </span>
                    <textarea value={meetingDescription} onChange={(event) => setMeetingDescription(event.target.value)} rows={5} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none", resize: "vertical", minHeight: "140px", maxHeight: "260px" }} />
                  </label>
                </>
              )}

              {type === "doc" && (
                <>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Title
                    </span>
                    <input value={docTitle} onChange={(event) => setDocTitle(event.target.value)} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none" }} />
                  </label>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Instruction
                    </span>
                    <textarea value={docPrompt} onChange={(event) => setDocPrompt(event.target.value)} rows={4} placeholder="Tell Saathi what this document should cover." style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none", resize: "vertical" }} />
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 14px", borderRadius: "16px", background: "#fafaf9", border: "1px solid #e7e5e4" }}>
                    <input type="checkbox" checked={generateDoc} onChange={(event) => setGenerateDoc(event.target.checked)} />
                    <span style={{ color: "#44403c" }}>Generate polished content with AI before creating the Google Doc</span>
                  </label>
                  <label style={{ display: "grid", gap: "8px" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#57534e", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      {generateDoc ? "Optional Notes" : "Content"}
                    </span>
                    <textarea value={docContent} onChange={(event) => setDocContent(event.target.value)} rows={10} placeholder={generateDoc ? "Optional notes, bullets, or source text to fold in." : "Write the exact document content."} style={{ width: "100%", borderRadius: "18px", border: "1px solid #d6d3d1", background: "white", padding: "16px 18px", fontSize: "1rem", outline: "none", resize: "vertical" }} />
                  </label>
                </>
              )}

              {error && (
                <div style={{ borderRadius: "16px", background: "#fef2f2", color: "#991b1b", border: "1px solid #fca5a5", padding: "12px 14px" }}>
                  {error}
                </div>
              )}
            </div>

            <div style={{ padding: isNarrow ? "0 18px 18px" : "0 28px 26px", display: "flex", justifyContent: "flex-end", gap: "12px", borderTop: "1px solid rgba(231,229,228,0.7)", background: "rgba(255,255,255,0.92)", flexDirection: isNarrow ? "column-reverse" : "row" }}>
              <button type="button" className="pill-btn secondary" onClick={onClose} style={{ justifyContent: "center" }}>
                <span>Cancel</span>
              </button>
              <button type="submit" className="pill-btn" style={{ minWidth: isNarrow ? "100%" : "180px", justifyContent: "center" }} disabled={submitting}>
                {submitting ? <LoaderCircle size={18} className="animate-spin" /> : <Icon size={18} />}
                <span>{submitting ? "Working..." : meta.title}</span>
              </button>
            </div>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
