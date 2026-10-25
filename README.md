# Ghost Data Still Exists
### HackerRank Orchestrate — October 2026 Hackathon

I built this project as part of the HackerRank Orchestrate hackathon, where the challenge was to investigate a problem that can easily go unnoticed: **a system can say someone's data has been deleted even when copies of that data still exist.**

A deletion request might be marked complete, but the data could remain in a database replica, an activity log, an export, an attachment, or an old backup. It can even reappear when systems synchronize or restore data.

I wanted to build a tool that looks beyond the reported status and checks the available evidence before deciding whether a deletion has actually been completed.

## What I built

Ghost Data Still Exists is a Python-based deletion-audit agent. It examines deletion requests alongside identity records, system activity, deletion policies, and supporting evidence to determine what happened to a user's data.

For every request, it produces one of three outcomes:

- **COMPLETE** — the available evidence supports that the required deletion and verification steps have been completed.
- **INCOMPLETE** — data remains, a required action is missing, or further remediation and verification are needed.
- **NOT_APPLICABLE** — the request does not actually ask for data deletion.

The output also includes an ordered list of findings, recommended remediation actions, and verification steps, with references to supporting evidence wherever required.

## How I approached the problem

Rather than treating a reported deletion status as the final answer, I built the solution around the evidence available in the dataset.

### 1. Checking whether deletion was actually requested

The first step is to classify the request itself. The classifier uses keyword, negation, and intent rules to distinguish deletion requests from other actions, such as accessing an account, correcting information, or withdrawing consent.

It includes multilingual rules for English, Spanish, Portuguese, French, Italian, German, Japanese, and Korean.

### 2. Looking for evidence across systems

The agent processes evidence from different formats, including SQL snapshots, JSON files, logs, CSV files, PDFs, text files, and images where OCR is available.

Each extracted fact is associated with information such as its timestamp, system, resource, state, and evidence reference. This lets the solution investigate the resource's state instead of relying only on a workflow's reported result.

### 3. Resolving user identities

A user's identity may change over time, so the solution checks both current identity records and historical audit records. It uses exact identifier matching to associate evidence with the correct subject and avoid confusing similar identities.

### 4. Applying deletion policies

Different types of data require different treatments. Depending on the applicable rule, the agent accounts for deletion, redaction, anonymization, or retention.

This matters because not every record should be physically deleted. Some records may need to be retained under an applicable policy, and their required state still needs to be checked.

### 5. Generating actionable results

Once the evidence has been processed, the solution builds an ordered sequence of findings, remediation actions, and verification checks.

The final result is written to `output.csv`, with one prediction for each of the 518 deletion requests in the supplied dataset.

## Technical implementation

I used Python to build a deterministic processing pipeline, with separate modules for classification, evidence extraction, identity resolution, policy handling, and step generation.

The main implementation decisions were:

- **Python** for the core processing pipeline.
- **Rule-based classification** for deletion intent and negation.
- **Structured evidence extraction** to work across different file formats.
- **Identity and audit-log matching** to account for historical identifiers.
- **Policy-driven processing** to determine the required treatment of each resource.
- **CSV and JSON output** to produce results in the format expected by the challenge.
- **Custom evaluation cases** to test behavior beyond the supplied sample examples.

The solution does not require an API key for its standard execution path. Optional LLM arbitration is available for ambiguous request text, but the shipped dataset does not contain cases that require it.

## Running the project

### Requirements

- Python 3.10 or newer
- Dependencies listed in `requirements.txt`
- Optional: Tesseract OCR for extracting text from image evidence

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Run the solution

Generate predictions for the full dataset:

```bash
python3 code/main.py --full
```

Run the public sample cases:

```bash
python3 code/main.py --sample
```

Inspect sample mismatches:

```bash
python3 code/main.py --sample --mismatches 99
```

Run the evaluation harness:

```bash
python3 code/evaluation/main.py
```

Run the additional custom test cases:

```bash
python3 code/evaluation/custom_cases.py
```

The full run generates `output.csv` in the repository root.

## Evaluation and what I learned

I evaluated the solution against the public sample output and added custom cases to check its behavior.

The implementation matches 17 of the 32 supplied sample cases exactly. The remaining discrepancies exposed an important limitation: some resource identifiers in the sample cases cannot be reliably mapped to users using the participant-visible evidence alone.

I documented this as a limitation rather than treating an inferred identity mapping as established fact.

Working on this problem also reinforced a few lessons for me:

- A successful operation is not the same as a verified outcome.
- Data spread across multiple systems makes identity resolution and evidence correlation difficult.
- Correctly applying a policy is just as important as identifying the current state of a resource.
- Evaluation needs to look at the sequence and quality of actions, not just the final classification.
- A system should distinguish between what the evidence establishes and what still needs investigation.

The evaluation details, additional test cases, and implementation limitations are documented in `code/evaluation/`.

## Current limitations

The main limitation is incomplete identity-to-resource attribution in some cases where the supplied evidence does not establish a reliable link. OCR can also introduce errors when extracting text from images.

These limitations affect how confidently certain resources can be attributed to a subject. Improving evidence correlation and developing stronger validation around ambiguous identity mappings would be important next steps.

## Repository structure

```text
.
├── code/
│   ├── main.py
│   ├── classify.py
│   └── evaluation/
│       ├── main.py
│       ├── custom_cases.py
│       ├── evaluation_report.md
│       └── usage_report.md
├── dataset/
├── problem_statement.md
└── README.md
```

The repository also contains the supporting implementation modules and configuration files required to run the solution.

## Final thoughts

This was a useful engineering challenge because it required more than classifying a request or checking a single database record. I had to think about how evidence from different systems fits together, how identity changes affect attribution, and how a result can be verified rather than simply assumed.

**The central idea behind Ghost Data Still Exists is simple: don't trust the deletion status alone — investigate the evidence.**
