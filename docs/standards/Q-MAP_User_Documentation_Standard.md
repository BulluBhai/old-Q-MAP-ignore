# Q-MAP User Documentation Standard

**Status:** permanent project requirement set by the Project Owner (Sandeep), 07-Nov-26.
**Applies to:** every document written for the Project Owner to follow. That includes installation and setup guides,
Windows operating instructions, Database Manager and Analytical Workbench guides, MIQP and QLOPB user guides, research
module manuals, data import and validation instructions, troubleshooting and recovery procedures, acceptance testing
and release procedures, and future Opportunity Scanner, Backtesting, Portfolio and Risk Analytics guides. It applies
even when the document is short.
**Where it is enforced:** `Q-MAP-Claude-Standing-Instructions.md` (loaded by `CLAUDE.md`) requires every user-facing
document to follow this standard.

## 1. Who the reader is

The Project Owner is a finance professional, not a software developer, and a beginner in Python. The Project Owner understands
markets, research requirements, quantitative concepts and business processes. The Project Owner should not be expected to understand
software terms, application architecture, folder structures, programming conventions or unstated technical
assumptions.

A document can be technically correct and still be unusable. The goal is that the Project Owner can do the task **correctly, safely
and independently**, without having to ask ChatGPT or Claude what the document meant.

**The acceptance test for every document:** can the Project Owner follow it from beginning to end, understand what they
are doing, recognise the correct result, save the required evidence, and know what to do if something goes wrong,
without someone explaining the instructions?

## 2. Rules

**A. Exact navigation.** For every action, name:
- which application to open (for example "Q-MAP Database Manager" or "Analytical Workbench", started from IDLE);
- which window or screen (for example **Sources** or **Datasets and Storage**);
- which section, using its numbered heading exactly as shown (for example "3. Options - parameters");
- the exact button or control, in **bold**, spelled exactly as on screen (for example **Reject (reversible)**);
- the full folder or file path where relevant (for example `D:\Q-MAP_V01\Q-MAP_OUTPUT\Data_Management\`).

**B. One action per step.** Use short numbered steps, one action each. Do not combine unrelated actions in one
paragraph. Do not leave out what happens between two steps.

**C. Say what the user should see.** After every important action, state:
- what appears on the screen, quoting the exact words, label or status;
- how to recognise success;
- whether the action is already complete, or whether another button, a confirmation dialog or a wait follows;
- what to do if the expected result does not appear.

**D. Use the words on the screen.** Use the labels Q-MAP and Windows actually show. If the document uses another word
(for example "settings"), say which on-screen label it means (for example "the section **3. Options - parameters**").
Explain any unavoidable technical term in plain English where it first appears.

**E. Name the right function and the wrong ones.** Where similar-looking modules, scanners or functions exist (for
example **Dataset Summary** and **MA Affinity (QLOPB)**), say exactly which one to use and which ones not to use.

**F. Say where the results are.** State where an output is saved, how to open it, and which file holds the value to
check (for example "the `Dataset_Summary_....csv` file in the run folder").

**G. Evidence, exactly.** For every check that needs evidence, state:
- what to keep: screenshot, CSV, PDF, text file, or a combination;
- the exact file name and the folder to save it in;
- what each item proves (for example "the PDF holds the full report and build line; the screenshot makes the build
  line easy to see");
- ready-to-copy wording for the tracker or record, where useful.

**H. Safety and recovery.** For every important operation, state:
- whether it changes data, the registry or settings;
- whether it can be undone, and how (for example "**Restore** undoes it");
- what not to click;
- what to do if something unexpected happens, including Windows messages such as "Replace the file in the
  destination?";
- when to stop and ask for help instead of continuing.

Clearly separate reversible actions from actions that could change or remove data. Never instruct an irreversible
change to the real registry or real data as part of a test. Original market files are only ever copied, never moved
or edited.

**I. Show it when words are not enough.** Where a folder layout, screen or sequence is hard to describe, add a folder
diagram, a table or an annotated screenshot. Do not add pictures for decoration.

**J. No assumptions, no invented details.** Never assume the reader knows where a file is stored, which window is
active, how to find a folder, what a technical term means, whether a button has already finished its work, or which
output file holds the result. **Every label, path, message and expected value must be checked against the actual
application (code or a real run) before the document is delivered.** If a detail cannot be checked, do not invent
it: mark it as unverified in the document and in the delivery report.

**K. No code, no logs.** Never require the reader to read Python code, run commands in a command window, or interpret
technical logs or error traces. If a log is evidence, the document says which file to keep, not how to read it.

**L. Consistent numbering.** Test or step numbers, evidence file names and tracker rows must match exactly across a
guide and its tracker or record sheet.

**M. Easier, not longer.** Make documents easier to follow, not merely longer.

## 3. Examples from UAT round 2c (07-Nov-26)

| Situation | What went wrong | What the document must do instead |
|---|---|---|
| Test 19: "copy all files from Market_Files into W8_Round2c three times" | The files were pasted three times into the same folder; Windows asked to replace files with the same names, so no extra copies were made | Give the exact folder layout (below), say why it is needed, and say what to do if Windows offers to replace files (click **Skip these files** or **Cancel**; never **Replace**) |
| Test 20: "open MA Affinity settings" | No heading called "Settings" exists; the screen shows **3. Options - parameters** | Use the on-screen heading and list the exact values to check: MA types SMA, MA start 10, MA end 250, forward windows 5, 10, 20, 50 |
| Test 21: "select ICICIBANK Daily and open Dataset Summary" | It was unclear whether to use Dataset Summary or the MA Affinity scanner | Say: use **Dataset Summary**, not MA Affinity; check both dates before **RUN ANALYSIS**; the numbers to compare are in the run's CSV file |
| Test 23: "check the build in the PDF and save a screenshot" | It was unclear whether the PDF itself had to be kept | Say: keep both. The PDF holds the full report and the build line; the screenshot makes the build line easy to see. Give both file names |
| Test 16: "reject the old duplicate" | After **Reject (reversible)**, the message "Rejected 1 dataset(s). ..." appeared; it was unclear whether a confirmation followed | Say: the action completes at once, with no confirmation dialog; the message and the live log confirm it; **Restore** undoes it |

Folder layout for a "many files" test such as test 19:

```text
D:\Q-MAP_V01\W8_Round2c\
    Copy_1\   (all 11 files from Market_Files)
    Copy_2\   (all 11 files again)
    Copy_3\   (all 11 files again)
```

That gives 33 files, and Windows never asks to replace anything, because each copy goes into its own folder.

## 4. Checklist before a document is delivered

- [ ] Written for the reader in section 1: plain English, terms explained where first used.
- [ ] Every action has exact navigation (rule A) and one action per step (rule B).
- [ ] Every important action says what the user should see and what to do if it differs (rules C, H).
- [ ] Every label, path, message and expected value checked against the application; anything unchecked is marked
      as unverified (rule J).
- [ ] Similar functions are distinguished, and result locations are given (rules E, F).
- [ ] Evidence: type, exact file name, folder and purpose for every check (rule G).
- [ ] Reversible and data-changing actions are clearly marked, with stop points (rule H).
- [ ] No code, commands or log reading required (rule K).
- [ ] Numbering and file names are consistent across guide and tracker (rule L).
- [ ] Read through once as a first-time Windows user with no programming knowledge.
- [ ] The delivery report states what was checked against the application and what could not be checked.
