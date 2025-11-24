## Take-Home Assessment: LLM-Powered Content Enrichment

**Your Core Task:** Develop a system that uses a Large Language Model (LLM) to automatically enrich draft articles with media and hyperlinks, focusing on robust data handling, effective prompt engineering, and clean, well-documented code.

---

### Your Mission

Build a pipeline to intelligently select and integrate visual media (images/videos) and informative hyperlinks into articles. You will strategically guide an LLM to make optimal content choices, including anchor text generation, based on relevance, context, provided keywords, and predefined guidelines.

---

### Development & Evaluation Note

You will receive a training set of two articles with associated resources to develop and test your solution. Your submitted system will then be evaluated on a separate, unseen test set of three articles.

---

### Key Objectives & Constraints

Produce a final, enriched Markdown article for each input, featuring:

- One **hero image**: a single, prominent image placed at the very beginning of the article, intended to capture attention and represent the article's main theme.
- One in-context image or video placed for maximum contextual value.
- Two contextual hyperlinks, with **LLM-generated anchor text around provided target keywords**, that enhance the content.

These three types of enrichments (one hero image, one in-context item, and two links with specified anchor text) are mandatory for each article. Relevant assets for these enrichments will always be available in the provided databases.

All selections, placements, and anchor text generation must be performed by the LLM based on relevance, context, and article content. Adherence to provided brand guidelines is also mandatory.

---

### Process Overview

Your general workflow will be:

1.  **Data Retrieval**: Access and shortlist potential media and link candidates from provided data (e.g., using SQL with .db files).
2.  **Prompt Engineering**: Craft precise instructions for the LLM to select assets, generate anchor text around target keywords, and specify placements.
3.  **Content Assembly**: Programmatically integrate the LLM's choices into the final Markdown article.
4.  **Quality Assurance**: Implement logging for observability and error handling for LLM responses.

---

### Provided Resources

Resources for training (indicative of test set structure):

- **Training Articles (e.g., article_1.md, article_2.md)**: Two draft articles, \~700 words each (Markdown, no existing links/media).
- **Target Keywords**: A list of target keywords for hyperlink anchor text generation, specific to each article.
- **media.db**: SQLite database with images and videos tables (id, url, title, description, tags, etc.).
- **links.db**: SQLite database with a resources table (id, url, title, description, topic_tags, type).
- **brand_rules.txt**: Text file with guidelines for voice, accessibility, and alt-text.
- **OpenRouter API Key**: Pre-loaded with $5.00 USD credit for development and experimentation.
  - _Note: Media/link descriptions are natural language; the LLM assesses relevance._

---

### Technical Environment

Your solution must be developed using **Python 3.11+** or later. Environment and dependency management should be handled using **uv** package manager. Use any external dependencies you may need.

---

### Development Guidance & Potential Challenges

Consider the following for your development process:

**Guidance for Development:**

- **Iterative Prompt Refinement:** Effective prompt engineering requires iteration. Experiment with phrasing and structure using training articles. A clearly defined, structured LLM output (e.g., JSON) is strongly advised for reliable parsing.
- **Thorough Use of Training Data:** Utilize the training articles comprehensively to validate all pipeline components, from data processing to final Markdown generation.
- **Effective LLM Direction:** The LLM's selections depend on article content and the provided descriptions for media/links. Your shortlisting strategy and prompt design are crucial for guiding the LLM effectively, including for anchor text generation.
- **Resilient Output Parsing:** Develop a robust strategy for parsing LLM output. Anticipate minor response variations, even with structured prompting, to ensure system reliability.

**Potential Challenges to Address:**

- **Dynamic Implementation:** The solution must operate dynamically. Avoid hardcoding asset identifiers, keywords (other than those provided for anchor text targeting), or insertion points, as these will not generalize to unseen test articles.
- **Adherence to Brand Guidelines:** Meticulously adhere to all stipulations in brand_rules.txt. Compliance is a key task requirement.
- **Efficient API Utilization:** The OpenRouter API key has finite credit. Use API calls efficiently during development (e.g., local testing of logic) to conserve this resource.
- **Comprehensive System Testing:** Thoroughly test your run.py script under various conditions using the training articles. A solution limited to few scenarios is incomplete.

---

### Submission Requirements

Submit the following:

| Component     | Description                                                                                                                                                                                                                                                                                                      |
| :------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **run.py**    | A well-structured Python script. Running this script (e.g., python run.py --article_path path/to/article.md --keywords_path path/to/keywords.txt) should process the input article and keywords, then output the enriched Markdown. The README must explain exact execution commands.                            |
| **README.md** | Concise document (max 400 words) detailing: \<br\> • Logic for selecting/shortlisting media and links. \<br\> • Prompt engineering strategy (including anchor text generation). \<br\> • Overview of logging and error handling. \<br\> • Clear instructions to run run.py, including environment setup with UV. |

