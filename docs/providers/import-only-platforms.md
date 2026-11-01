# Providers: LinkedIn, Indeed, Wellfound, Naukri (user import only)

One page for the four platforms where no automated access is built. For each, jobs are supported only when the person copies or exports them themselves (paste, URL of a single job they are viewing, CSV or XLSX), and are always labelled "imported by you". Each is recorded in the registry with its terms address and what was read on 2026-11-02.

| Field | LinkedIn | Indeed | Wellfound | Naukri |
|---|---|---|---|---|
| Role in Provenance | User import only | User import only | User import only | User import only |
| Terms URL | https://www.linkedin.com/legal/user-agreement | https://www.indeed.com/legal | https://wellfound.com/terms | https://www.naukri.com/termsconditions |
| Read | Yes, the User Agreement | Part: about 200,000 of 349,000 characters | Yes, the terms | No. The page returned HTTP 403 |
| What the terms say about automation | Forbid bots, crawlers and scripts that scrape or copy the service, other automated access, circumventing limits, and reusing data through aggregators without consent | Forbid scraping the database in the sourcing product and automating the apply process except through Indeed's vendors. Developers must follow the Indeed Developer Terms and API documentation (docs.indeed.com) | Forbid copying content, collecting it by scraping or other automated means, using automated systems beyond a normal browser, and commercial or competitive use of content | Unknown. Not read |
| Official job search API found | No | None for this product found or verified | No | None known |
| Compliance status in the registry | prohibited | prohibited | prohibited | unverified |
| Capability class | USER_PROVIDED_URL or USER_PROVIDED_EXPORT, MANUAL_INPUT | same | same | same |
| Current integration status | No automation built or planned | same | same | same |
| Next review due | When the terms change, or for a partner program the owner joins | Read the remaining 149,000 characters (carryover C-36) | Same as LinkedIn | Read the page (carryover C-36) |

## Notes
- The browser extension idea in the compliance document stays undecided. Each target site's terms would need to be read first, and the four terms above already forbid automated collection.
- Indeed and Naukri may offer partner programs. If the owner pursues one, it becomes a new verification record.
