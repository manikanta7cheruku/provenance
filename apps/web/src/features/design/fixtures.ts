// Sample data for the design prototypes. Every name here is invented. Nothing is loaded from the API.
import type { Tone } from "../../ui";

export type WorkMode = "Remote" | "Hybrid" | "On-site";
export type Band = "Strong match" | "Good match" | "Review" | "Not recommended" | "Not eligible";

export const BAND_TONE: Record<Band, Tone> = {
  "Strong match": "ok",
  "Good match": "ok",
  Review: "warn",
  "Not recommended": "neutral",
  "Not eligible": "danger",
};

export interface SampleJob {
  id: string;
  title: string;
  company: string;
  place: string;
  workMode: WorkMode;
  band: Band;
  /** One sentence produced by code from the stored result, never written by the model. */
  reason: string;
  met: number;
  required: number;
  /** Where the posting came from and how it reached the app. Stored separately and shown honestly. */
  source: string;
  acquisition: string;
  updated: string;
  gates: { name: string; result: "Passed" | "Needs your input" | "Blocked"; detail: string }[];
}

export const SAMPLE_JOBS: SampleJob[] = [
  {
    id: "j1",
    title: "Data Analyst, Early Careers",
    company: "Fernlight Systems",
    place: "Bengaluru, India",
    workMode: "Hybrid",
    band: "Review",
    reason: "3 of 6 requirements are supported by direct evidence. 1 is partly supported, 1 is not verified and 1 conflicts with other evidence.",
    met: 3,
    required: 6,
    source: "Wellfound",
    acquisition: "Pasted by you",
    updated: "Today",
    gates: [
      { name: "Work authorization", result: "Passed", detail: "The posting accepts candidates authorized to work in India. Your profile says you are." },
      { name: "Location", result: "Passed", detail: "Hybrid in Bengaluru. Your preferences include Bengaluru." },
      { name: "Employment type", result: "Passed", detail: "Full time. Matches your preferences." },
      { name: "Exclusions", result: "Passed", detail: "None of your exclusions appear in the posting." },
    ],
  },
  {
    id: "j2",
    title: "Junior Backend Engineer",
    company: "Kestrel Analytics",
    place: "Remote, India",
    workMode: "Remote",
    band: "Strong match",
    reason: "9 of 10 required requirements are supported by direct evidence.",
    met: 9,
    required: 10,
    source: "Greenhouse",
    acquisition: "Fetched from the company board",
    updated: "Today",
    gates: [
      { name: "Work authorization", result: "Passed", detail: "Open to candidates in India." },
      { name: "Location", result: "Passed", detail: "Remote within India." },
      { name: "Employment type", result: "Passed", detail: "Full time." },
      { name: "Exclusions", result: "Passed", detail: "No exclusions found." },
    ],
  },
  {
    id: "j3",
    title: "Machine Learning Intern",
    company: "Mapleton Health",
    place: "Toronto, Canada",
    workMode: "On-site",
    band: "Not eligible",
    reason: "The posting requires work authorization in Canada, which your profile does not state.",
    met: 5,
    required: 8,
    source: "LinkedIn",
    acquisition: "Imported by you from a CSV file",
    updated: "Yesterday",
    gates: [
      { name: "Work authorization", result: "Blocked", detail: "Requires Canadian work authorization. Your profile says you are authorized in India only." },
      { name: "Location", result: "Needs your input", detail: "On-site in Toronto. Your preferences say relocation is not decided." },
      { name: "Employment type", result: "Passed", detail: "Internship. Matches your preferences." },
      { name: "Exclusions", result: "Passed", detail: "No exclusions found." },
    ],
  },
  {
    id: "j4",
    title: "Software Engineer, Platform",
    company: "Harbor and Pine",
    place: "Hyderabad, India",
    workMode: "On-site",
    band: "Review",
    reason: "5 of 9 required requirements are supported. 3 are not verified.",
    met: 5,
    required: 9,
    source: "Company career page",
    acquisition: "Pasted by you",
    updated: "2 days ago",
    gates: [
      { name: "Work authorization", result: "Passed", detail: "Open to candidates in India." },
      { name: "Location", result: "Passed", detail: "On-site in Hyderabad. Your preferences include Hyderabad." },
      { name: "Employment type", result: "Passed", detail: "Full time." },
      { name: "Exclusions", result: "Passed", detail: "No exclusions found." },
    ],
  },
  {
    id: "j5",
    title: "Associate Product Analyst",
    company: "Quill and Ledger",
    place: "Pune, India",
    workMode: "Hybrid",
    band: "Not recommended",
    reason: "3 of 8 required requirements are supported. The role asks for 4 or more years of experience.",
    met: 3,
    required: 8,
    source: "Naukri",
    acquisition: "Pasted by you",
    updated: "3 days ago",
    gates: [
      { name: "Work authorization", result: "Passed", detail: "Open to candidates in India." },
      { name: "Location", result: "Passed", detail: "Hybrid in Pune." },
      { name: "Employment type", result: "Passed", detail: "Full time." },
      { name: "Exclusions", result: "Passed", detail: "No exclusions found." },
    ],
  },
  {
    id: "j6",
    title: "Frontend Developer",
    company: "Tidewater Labs",
    place: "Remote, worldwide",
    workMode: "Remote",
    band: "Good match",
    reason: "6 of 8 required requirements are supported. 2 are partly supported.",
    met: 6,
    required: 8,
    source: "Remotive",
    acquisition: "Fetched from the Remotive feed",
    updated: "3 days ago",
    gates: [
      { name: "Work authorization", result: "Passed", detail: "Open worldwide." },
      { name: "Location", result: "Passed", detail: "Remote." },
      { name: "Employment type", result: "Passed", detail: "Contract. Your preferences include contract work." },
      { name: "Exclusions", result: "Passed", detail: "No exclusions found." },
    ],
  },
];

export type Verdict = "Met" | "Partial" | "Not verified" | "Conflicting" | "Blocker";
export const VERDICT_TONE: Record<Verdict, Tone> = {
  Met: "ok",
  Partial: "warn",
  "Not verified": "neutral",
  Conflicting: "warn",
  Blocker: "danger",
};

export type EvidenceKind = "Direct" | "Inferred" | "Missing" | "Conflicting";

export interface SampleEvidence {
  kind: EvidenceKind;
  /** The sentence from the user's own profile. Empty for missing evidence. */
  quote: string;
  from: string;
  provenance: "From your resume" | "Added or edited by you";
}

export interface SampleRequirement {
  id: string;
  text: string;
  required: boolean;
  postingQuote: string;
  verdict: Verdict;
  confidence: "High" | "Medium" | "Low" | "Not enough evidence";
  /** Generated by code from the evidence properties, never from the model's own confidence. */
  confidenceWhy: string;
  evidence: SampleEvidence[];
  missing?: string;
  suggestion?: string;
}

export const SAMPLE_REQUIREMENTS: SampleRequirement[] = [
  {
    id: "r1",
    text: "Write SQL queries to analyze data",
    required: true,
    postingQuote: "You will write SQL to answer questions from product and operations teams.",
    verdict: "Met",
    confidence: "High",
    confidenceWhy: "Two direct statements in your profile name SQL work, and one of them includes a result you measured.",
    evidence: [
      {
        kind: "Direct",
        quote: "Wrote SQL joins and window functions over 1.2 million order rows to find late deliveries.",
        from: "Project: Delivery delay report",
        provenance: "From your resume",
      },
      {
        kind: "Direct",
        quote: "Completed a SQL course covering joins, subqueries and indexing.",
        from: "Certification: SQL for data analysis",
        provenance: "Added or edited by you",
      },
    ],
  },
  {
    id: "r2",
    text: "Build dashboards in a BI tool",
    required: true,
    postingQuote: "Experience with Tableau, Power BI or a similar tool.",
    verdict: "Partial",
    confidence: "Medium",
    confidenceWhy: "The evidence names a charting library, not a BI tool. The posting allows similar tools, so it counts in part.",
    evidence: [
      {
        kind: "Inferred",
        quote: "Built an interactive sales chart page with Plotly and a filter panel.",
        from: "Project: Sales explorer",
        provenance: "From your resume",
      },
    ],
    missing: "A dashboard built in a BI tool, or a statement that you have used one.",
    suggestion: "If you have used Power BI or Tableau in a course, add it to your profile with what you built.",
  },
  {
    id: "r3",
    text: "Communicate findings to non-technical teams",
    required: true,
    postingQuote: "You will present findings to managers and operations leads.",
    verdict: "Met",
    confidence: "Medium",
    confidenceWhy: "One direct statement. No second source confirms it.",
    evidence: [
      {
        kind: "Direct",
        quote: "Presented the delay analysis to a panel of 12 faculty and industry mentors.",
        from: "Project: Delivery delay report",
        provenance: "From your resume",
      },
    ],
  },
  {
    id: "r4",
    text: "Statistics fundamentals",
    required: true,
    postingQuote: "Solid grounding in statistics, including hypothesis testing.",
    verdict: "Not verified",
    confidence: "Not enough evidence",
    confidenceWhy: "Your profile mentions a statistics course title but nothing you did with it.",
    evidence: [{ kind: "Missing", quote: "", from: "No matching statement found", provenance: "From your resume" }],
    missing: "A project, result or course detail that shows hypothesis testing.",
    suggestion: "Add one sentence about where you used a hypothesis test, if you did.",
  },
  {
    id: "r5",
    text: "Python for data work",
    required: true,
    postingQuote: "Comfortable with Python and pandas.",
    verdict: "Met",
    confidence: "High",
    confidenceWhy: "Three direct statements across two projects and one internship.",
    evidence: [
      {
        kind: "Direct",
        quote: "Cleaned and merged six CSV sources with pandas before analysis.",
        from: "Internship: Data intern, Mapleton Retail",
        provenance: "From your resume",
      },
    ],
  },
  {
    id: "r6",
    text: "Based in Bengaluru or willing to relocate",
    required: true,
    postingQuote: "This is a hybrid role based in our Bengaluru office.",
    verdict: "Conflicting",
    confidence: "Low",
    confidenceWhy: "Your resume lists Chennai. Your preferences list Bengaluru. They disagree and neither is confirmed.",
    evidence: [
      { kind: "Conflicting", quote: "Chennai, Tamil Nadu", from: "Resume header", provenance: "From your resume" },
      { kind: "Direct", quote: "Preferred locations: Bengaluru, Hyderabad", from: "Preferences", provenance: "Added or edited by you" },
    ],
    missing: "Confirmation that you can be in Bengaluru.",
    suggestion: "Confirm your current location in your profile, or say you are open to relocating.",
  },
];

export const SAMPLE_GAPS = [
  {
    title: "Show hypothesis testing",
    why: "The posting lists statistics as required and nothing in your profile shows it.",
    action: "Add a short project or exercise where you ran and explained a t-test or chi-squared test, then add it to your profile.",
  },
  {
    title: "Show one BI tool",
    why: "The posting names Tableau or Power BI. Your evidence names a charting library.",
    action: "Build one dashboard in a free BI tool from a public dataset and add a link and a sentence about what it shows.",
  },
];
