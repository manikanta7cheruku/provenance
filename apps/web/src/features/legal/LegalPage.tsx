import { Link } from "react-router-dom";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { BrandMark, Notice } from "../../ui";
import { PRIVACY, TERMS } from "./content";
import type { LegalDocument } from "./content";
import "./legal.css";

const slug = (title: string) => `h-${title.replace(/\W+/g, "-")}`;

function LegalPage({ doc }: { doc: LegalDocument }) {
  useDocumentTitle(doc.title);
  const other =
    doc === PRIVACY
      ? { to: "/terms", label: "Terms of use" }
      : { to: "/privacy", label: "Privacy policy" };
  return (
    <div className="legal">
      <header className="legal__header">
        <Link to="/" className="legal__brand">
          <BrandMark size={28} />
          Provenance
        </Link>
      </header>
      <main id="main" className="legal__main">
        <h1>{doc.title}</h1>
        <p className="legal__lede">{doc.summary}</p>
        <p className="field__hint">
          Version {doc.version}, updated {doc.updated}.
        </p>
        <Notice tone="warn" title="Open before launch">
          <ul>
            {doc.open.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Notice>
        {doc.sections.map((section) => (
          <section key={section.title} aria-labelledby={slug(section.title)}>
            <h2 id={slug(section.title)}>{section.title}</h2>
            {section.paragraphs?.map((p) => (
              <p key={p}>{p}</p>
            ))}
            {section.items ? (
              <ul>
                {section.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
        <nav aria-label="Legal" className="legal__nav">
          <Link to={other.to}>{other.label}</Link>
          <Link to="/">Back to Provenance</Link>
        </nav>
      </main>
    </div>
  );
}

export const PrivacyPage = () => <LegalPage doc={PRIVACY} />;
export const TermsPage = () => <LegalPage doc={TERMS} />;
