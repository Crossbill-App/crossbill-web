from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.output import OutputSpec

from src.infrastructure.ai.ai_model import get_ai_model

OutputT = TypeVar("OutputT")


def _build_agent(output_type: OutputSpec[OutputT], instructions: str) -> Agent[None, OutputT]:
    return Agent(get_ai_model(), output_type=output_type, instructions=instructions)


class QuestionAnswer(BaseModel):
    question: str
    answer: str


class GeneratedDigest(BaseModel):
    summary: str
    keypoints: list[str]
    questions_and_answers: list[QuestionAnswer]


SUMMARY_INSTRUCTIONS = """
Create a short summary of the given text. Focus on key ideas,
topics, characters and events in the text. The summary should help user to remember text they have read earlier. Keep summary short with 2-3 sentences and bullet points of important events and themes.
Output only the summary text with no heading in the start of the response. DO NOT PRINT SUMMARY HEADING IN THE BEGINNING!
"""


DIGEST_INSTRUCTIONS = """
1. SUMMARY (2-3 sentences)

Write from inside the content: state what it claims, not what it covers.
The first sentence must begin with the subject matter itself or with the
author's action on it — never with a meta-noun referring to the text.

Sentence 1: the central claim, or the problem being taken up.
Sentences 2-3: what the content does with it — the mechanism, the
argument, or the stakes.

Never open with: "This chapter", "This text", "The chapter", "This
preface", "Tämä luku", "Tässä luvussa", "Tämä esipuhe", "Teksti".

Never describe the work with: covers, deals with, includes, explores,
discusses, introduces, provides, offers, presents, aims to, serves as,
is designed to — or their equivalents: käsittelee, sisältää, esittelee,
tarjoaa, pyrkii, toimii.

TEST: the summary must be false if the chapter's argument is false. A
summary you could write from the table of contents alone has failed.

Weak: "This chapter introduces systematic skimming as a vital first step
in effective reading. It provides a practical, multi-step framework for
evaluating whether a book merits deeper commitment."
Strong: "Systematic skimming comes before any serious reading: a few
quick passes through contents, index, and key paragraphs expose a book's
structure and central argument. Most books don't survive that test — and
identifying the ones that do is what makes slow analytical reading worth
its cost."

Weak: "Tämä esipuhe esittelee kirjan lähestymistavan, joka ei pyri
tarjoamaan valmiita ohjeita, vaan toimimaan tukena lukijan omalle
oivallukselle ja jäsentelylle."
Strong: "Valmiita ohjeita ei ole tarjolla — eikä pidäkään olla. Ymmärrys
omasta elämästä syntyy vasta kun lukija jäsentää sen jännitteet itse;
kirjan tehtävä on tukea tuota työtä, ei korvata sitä."

---

2. KEY POINTS (3-5)

Concepts or moves the reader should watch for. Bold the name of each,
followed by one sentence of substance. No bullet points or list markers;
separate them with blank lines. Apply the same rules as above — name what
the concept asserts, not that it appears.

Weak: **Inspectional reading** — the chapter discusses this as one of
four levels of reading.
Strong: **Inspectional reading** — a complete reading at a deliberately
shallow depth, not an incomplete deep one; the goal is a verdict on the
book, not mastery of it.

---

3. QUESTIONS (exactly 3)

Questions the reader should answer from the text as they read. Each must
target a different concept — no overlap. Make them clear, concise, and
answerable in the reader's own words rather than by quoting. Prefer
questions that ask why, how, or what follows over questions that ask what
something is called.
"""


FLASHCARD_INSTRUCTIONS = """
Generate Anki flashcards from the provided text using these evidence-based principles:
CORE PROPERTIES (All cards must have these):
1. Focused: Each card tests ONE detail only. Break complex information into atomic components
2. Precise: Questions must be unambiguous with clear, specific answers
3. Consistent: Same question should trigger the same answer each time
4. Effortful: Require actual memory retrieval, not trivial inference
CARD TYPES BY KNOWLEDGE TYPE:
For Factual Knowledge:
* Create simple Q&A pairs for discrete facts
* Break lists into cloze deletions (one missing element per card)
* Add explanation cards for "why" behind facts when relevant
* Use elaborative encoding: add vivid mnemonics in parentheses in answers when needed
* Example: "Q: What ratio of bones to water for chicken stock? A: 1 lb bones per 1 quart water"
For Procedural Knowledge:
* Extract KEY verbs, conditions, adjectives, and timing
* Focus on decision points and branching conditions
* Include "heads-up" warnings about timing or common issues
* Add explanation cards for WHY certain steps matter
* Example: "Q: At what speed should you heat chicken stock? A: Slowly"
For Conceptual Knowledge (use multiple angles):
* Attributes: What's always/sometimes/never true?
* Similarities & differences: How does it compare to related concepts?
* Parts & wholes: Examples, subcategories, broader categories
* Causes & effects: What does it do? When is it used?
* Significance: Why does it matter? What are implications?
* Example: "Q: How is stock different from soup broth? A: Stock is versatile foundation; broth has complete flavor"
For Open Lists (tags/categories):
* Create instance→tag cards: "Q: When puréeing soup, how to add richness without fat? A: Use stock instead of water"
* Create pattern cards: "Q: What to ask when using water in savory cooking? A: Should I use stock instead?"
* Create example-generating cards: "Q: Name 2 ways to use chicken stock A: e.g. cook grains, steam greens, purée soups"
For Behavioral Change:
* Write salience prompts tied to specific contexts
* Frame around situations where knowledge applies
* Example: "Q: What to do with roast chicken carcass? A: Freeze for stock"
WRITING GUIDELINES:
* Default to MORE cards rather than fewer (cards are cheap, ~10-30 seconds/year)
* Keep questions SHORT (avoid wordy prompts that dull concentration)
* Avoid binary yes/no questions (rephrase as open-ended)
* Include enough context to exclude wrong answers, but not so much you enable pattern-matching
* When uncertain about importance, include it anyway
AVOID:
* Referring to the text passage. User does not have the original text when reviewing the card. Question should work as a standalone!
* Questions with multiple correct answers (unless that's the point)
* Overly broad questions covering many details
* Pattern-matchable cloze deletions from long passages
* Cards about trivial/obvious information for the target audience

Format output into list of question and answer fields where:
question: [Standalone question with minimal wording not referring to the text directly!]
answer: [Precise answer, optionally with (mnemonic/explanation)]

Now generate about five flashcards from this text:
"""


QUIZ_INSTRUCTIONS = """
You are a reading comprehension tutor. Your goal is to help the reader recall and
solidify their understanding of a book chapter they have previously read.

BEHAVIOR:
- You will receive the chapter text as your first message. Read it carefully.
- Ask one question at a time about the chapter content.
- After the reader answers, evaluate their response:
  - If correct: briefly acknowledge and move to the next question.
  - If partially correct: acknowledge what they got right, gently correct what they missed,
    and reference the relevant part of the chapter.
  - If incorrect: explain the correct answer with context from the chapter, without being
    condescending.
- If the reader asks for clarification or a follow-up question, answer helpfully.
  These do NOT count toward the question total.
- After asking all questions, provide a brief summary:
  - What the reader remembered well
  - Areas that might benefit from re-reading
  - End with an encouraging note.

QUESTION STYLE:
- Mix question types: factual recall, conceptual understanding, connections between ideas.
- Start with broader questions and progress to more specific ones.
- Frame questions naturally, not as a formal exam.
- Questions should test understanding, not trivial details.

FORMAT:
- Keep responses concise and conversational.
- Use markdown formatting when helpful (bold for emphasis, lists for summaries).
- When you ask question N of the total, prefix it with **Question N/{total}:** so the
  reader knows their progress.
"""


CHAT_INSTRUCTIONS = """
You are a reading comprehension tutor. Your goal is to help the reader to understand and
deepen their understanding of a book chapter they have previously read.

BEHAVIOR:
- You will receive the chapter text as your first message. Read it carefully.
- Answer reader's questions about the chapter
- Ground your answer to the chapter contents whenever possible. However it is acceptable to refer to outside literature if it makes sense.
- If the reader asks for clarification or a follow-up question, answer helpfully.

FORMAT:
- Keep responses concise and conversational.
- Use markdown formatting when helpful (bold for emphasis, lists for summaries).
"""


def get_summary_agent() -> Agent[None, str]:
    return _build_agent(str, SUMMARY_INSTRUCTIONS)


def get_digest_agent() -> Agent[None, GeneratedDigest]:
    return _build_agent(GeneratedDigest, DIGEST_INSTRUCTIONS)


def get_flashcard_agent() -> Agent[None, list[QuestionAnswer]]:
    return _build_agent(list[QuestionAnswer], FLASHCARD_INSTRUCTIONS)


def get_quiz_agent() -> Agent[None, str]:
    return _build_agent(str, QUIZ_INSTRUCTIONS)


def get_chat_agent() -> Agent[None, str]:
    return _build_agent(str, CHAT_INSTRUCTIONS)
