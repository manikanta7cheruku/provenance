// The privacy policy and the terms, as data. They describe what the product really does today and
// are a draft until a lawyer has read them (carryover C-155). Anything not yet decided is listed
// under "Open before launch" on the page, not hidden in the text.

export interface LegalSection {
  title: string;
  paragraphs?: string[];
  items?: string[];
}

export interface LegalDocument {
  title: string;
  summary: string;
  version: string;
  updated: string;
  open: string[];
  sections: LegalSection[];
}

export const LEGAL_VERSION = "0.1 (draft)";
export const LEGAL_UPDATED = "6 November 2026";

export const PRIVACY: LegalDocument = {
  title: "Privacy policy",
  summary:
    "What Provenance keeps about you, why, who else sees it, for how long, and what you can do about it.",
  version: LEGAL_VERSION,
  updated: LEGAL_UPDATED,
  open: [
    "A lawyer has not yet read this policy.",
    "The contact address for privacy questions is added before launch.",
    "The model provider plan and its terms about training are confirmed before launch (see the section on who else handles your data).",
  ],
  sections: [
    {
      title: "What we keep",
      items: [
        "Your account: your email address, and your password as a one-way hash. We cannot read your password.",
        "What you add: your profile entries and preferences, the resume files you upload and the text read from them, pictures you add to a resume, resumes you make in the studio, jobs you paste, import or bring in, your decisions and notes about them, drafts, preparation notes and saved views.",
        "If you connect GitHub: the repositories you choose and the text you choose to bring in. The access token is kept encrypted. Provenance asks for no permission to change anything on GitHub.",
        "Records of use: when you sign in, a keyed hash of your network address (not the address itself), and a record of actions such as a security rejection, a download of your data or a deletion request. Counts of model calls and their cost are kept without any of the text.",
      ],
    },
    {
      title: "Cookies and your device",
      paragraphs: [
        "Provenance sets one cookie, which keeps you signed in. It is secure, not readable by scripts on the page, and not used to follow you. Your light or dark choice is kept on your own device. There are no advertising or analytics cookies.",
      ],
    },
    {
      title: "Why we use it",
      items: [
        "To run what you asked for: reading a job, checking it against your evidence, tailoring a resume, writing a draft, preparing for an interview, making a report.",
        "To keep the service safe and fair: limits on how much can be used, protection against abuse, and finding faults.",
        "We do not sell your data, show advertising, or build a profile of you for anyone else.",
      ],
    },
    {
      title: "Who else handles your data",
      items: [
        "A model provider. When you use a feature that reads or writes text, the relevant text (a posting, and the entries of your profile that matter to it) is sent to the provider model to produce the result. The terms of the provider plan we use say what it may do with that text. Until we use a paid plan whose terms say inputs are not used to train models, do not enter anything you would not want a provider to see.",
        "An email service, to send you sign-in and password messages.",
        "The company that hosts the servers and stores the files and backups.",
        "GitHub, only if you connect it.",
        "Administrators can see how the service is doing (counts, errors, queue state) and manage accounts. They cannot open your resumes, jobs or notes.",
        "We may have to share information if the law requires it.",
      ],
    },
    {
      title: "How it is protected",
      paragraphs: [
        "Connections are encrypted. Your documents are kept in private storage. Each person's data is separated in the database itself, so a mistake in the application cannot show one person the data of another. Connector tokens are encrypted with a key that is kept apart from the database. No system is perfectly safe, and we will tell you if something affecting you goes wrong.",
      ],
    },
    {
      title: "How long we keep it",
      items: [
        "Until you delete it. Deleting your account removes your profile, resumes, jobs, drafts, files and everything else you added, and signs you out everywhere. It takes a few minutes and cannot be undone.",
        "Reports you ask for are deleted after 7 days.",
        "Sign-in sessions end after 7 days without use or 30 days at most.",
        "Backups keep a copy for up to 30 days after it is deleted from the live service, and then it is gone. A backup is only used to recover from a disaster.",
        "After deletion we keep a record that a deletion happened, with no name, email or identifier, and counts of model calls without any text.",
      ],
    },
    {
      title: "Your choices",
      items: [
        "Download a copy of your data from Settings, Your data.",
        "Delete your account from the same place.",
        "Correct or remove anything you added at any time in the product.",
        "Ask us a question or raise a concern using the contact address that is added before launch.",
      ],
    },
    {
      title: "Children",
      paragraphs: [
        "Provenance is not meant for anyone under 16 and we do not knowingly keep their data.",
      ],
    },
    {
      title: "Changes",
      paragraphs: [
        "When this policy changes in a way that matters, we will say so in the product before it takes effect. The version and date are at the top.",
      ],
    },
  ],
};

export const TERMS: LegalDocument = {
  title: "Terms of use",
  summary: "The rules for using Provenance, in plain words.",
  version: LEGAL_VERSION,
  updated: LEGAL_UPDATED,
  open: [
    "A lawyer has not yet read these terms.",
    "The company name, the contact address and the law that governs these terms are added before launch.",
    "Paid plans and their terms do not exist yet. Nothing is charged today.",
  ],
  sections: [
    {
      title: "What Provenance is",
      paragraphs: [
        "Provenance helps you look for jobs and shows, for each match, the evidence behind it. It is a tool for you to use. It does not apply for jobs for you, send messages for you or speak for you.",
      ],
    },
    {
      title: "Your account",
      items: [
        "Keep your password to yourself. You are responsible for what happens under your account.",
        "Give a real email address. Sign-up may be by invitation.",
        "You can delete your account at any time from Settings.",
      ],
    },
    {
      title: "What you put in",
      items: [
        "What you add stays yours. You give us permission to store it and to process it to provide the service to you, as the privacy policy describes.",
        "Only add things you have the right to use. Do not add private information about other people.",
        "Do not use Provenance to break the law, to attack or overload it, to try to reach the data of other people, or to bypass its limits.",
      ],
    },
    {
      title: "Results are help, not advice",
      paragraphs: [
        "Matches, scores, tailoring suggestions, drafts and preparation material are produced by rules and by language models, and they can be wrong or incomplete. Each shows its evidence so you can check it. Read everything before you rely on it or send it. Provenance does not promise you an interview or a job. Not shown never means you cannot do something: it means your profile does not say so yet.",
      ],
    },
    {
      title: "Job sources",
      paragraphs: [
        "Jobs come from sources that allow it, and from postings you bring in yourself. A posting belongs to whoever published it. Always check the original posting before you apply.",
      ],
    },
    {
      title: "Limits and plans",
      paragraphs: [
        "Each plan has monthly limits on the things that cost us money to run. When you reach one, you are told what you used and when it restarts. Reading, editing and downloading what you already have is never counted. We may change the limits, and we will tell you first.",
      ],
    },
    {
      title: "Availability",
      paragraphs: [
        "We work to keep Provenance running, but it is provided as it is and may be interrupted, changed or ended. Keep your own copy of anything important: you can download your data at any time.",
      ],
    },
    {
      title: "Ending",
      paragraphs: [
        "You can stop at any time by deleting your account. We may suspend or remove an account that breaks these terms or harms others or the service, and we will say why where we can.",
      ],
    },
    {
      title: "Responsibility",
      paragraphs: [
        "As far as the law allows, we are not responsible for losses that come from relying on results, from a posting being wrong, or from the service being unavailable. Nothing here limits what the law does not allow us to limit.",
      ],
    },
    {
      title: "Changes",
      paragraphs: [
        "When these terms change in a way that matters, we will say so in the product before it takes effect. The version and date are at the top.",
      ],
    },
  ],
};
