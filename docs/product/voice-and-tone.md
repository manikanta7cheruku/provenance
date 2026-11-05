# Voice and tone

The words in the interface are part of the design. They are written for a person who is busy, careful and a little tired of software that talks too much.

## Principles
1. **Plain.** Short words, short sentences. No jargon the person did not choose.
2. **Specific.** Say what happened, to what, and what to do. "The picture is over 24 megapixels. Choose a smaller one." not "Something went wrong."
3. **Calm.** No exclamation marks, no apologies for things that are not our fault, no alarm. Errors are information.
4. **Honest.** Say what is not known. Machine-written text is labelled as a draft written from the person's evidence, to be checked. The interface does not call itself intelligent, smart or magic.
5. **Respectful.** The person is in charge. Offer, do not nag. Confirm before anything that cannot be undone.
6. **Consistent.** One name for one thing. Evidence, job, resume, draft, theme.

## Words we do not use
Hype and filler: the stock marketing vocabulary of software launches, words that call the product intelligent or magical, cute apologies, emoji and exclamation marks. The list is kept in `apps/web/scripts/check-copy.mjs`, and `npm run check:copy` refuses it in the interface and the docs.

## Patterns
- **Button labels** are verbs and name the object when there is more than one: "Save this look", "Delete it, Forest look".
- **Empty states** say what this place is for and give the one next step.
- **Errors** give the problem, then the fix, in that order, without blame.
- **Success** is short and says what changed: "Saved as Interview blue."
- **Confirmations** name the thing and the consequence: "Resumes that used it keep their colors."
- **Numbers** are exact where it matters and plain where it does not.
- **Dates** are written out where there could be doubt.

## Names
The product is Provenance. The line is "Jobs, with receipts": every claim about a job points back to where it came from.
