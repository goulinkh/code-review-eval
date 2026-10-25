# Fixture diagrams

These six Mermaid diagrams explain the fixture format to an audience. Each
diagram covers a different level of detail.

## 1. System architecture — What is a fixture?

```mermaid
flowchart TD
    fixture["Evaluation Fixture"]

    subgraph reviewer_data["Reviewer-facing data"]
        input_json["reviewer/input.json<br/>Review task + repository state"]
        prefix_json["reviewer/prefix.json<br/>Previous conversation (optional)"]
    end

    subgraph source_content["Source content"]
        blobs["environment/blobs/<br/>Content-addressed files"]
    end

    subgraph private_data["Private evaluation data"]
        expectations_json["private/expectations.json<br/>Expected findings + evaluation rules"]
    end

    agent["Code Review Agent"]
    file_service["Tool / File Service"]
    grader["Private Grader"]

    fixture --> input_json
    fixture --> prefix_json
    fixture --> blobs
    fixture --> expectations_json
    input_json --> agent
    prefix_json -->|Continuation only| agent
    blobs --> file_service
    file_service -->|Permitted file reads| agent
    agent -->|Review output| grader
    expectations_json --> grader

    classDef start_point fill:#334155,stroke:#334155,color:#ffffff
    classDef public fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef storage fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef private fill:#fee2e2,stroke:#dc2626,color:#991b1b
    classDef actor fill:#dcfce7,stroke:#16a34a,color:#166534

    class fixture start_point
    class input_json,prefix_json public
    class blobs storage
    class expectations_json,grader private
    class agent,file_service actor
```

## 2. Evaluation lifecycle — How does a review run?

```mermaid
flowchart TD
    begin_eval(["Start Evaluation"])
    load_input["Load reviewer/input.json"]
    start_mode{"Start mode?"}
    fresh["Fresh<br/>New conversation"]
    continuation["Continuation<br/>Restore prefix.json"]
    protocol{"Review protocol?"}
    fixed_context["Fixed-context<br/>Use supplied context"]
    tool_enabled["Tool-enabled<br/>Access permitted files"]
    budgets["Enforce remaining budgets"]
    analyze["Reviewer analyzes code change"]
    findings["Produce review findings"]
    grader["Private grader evaluates output"]
    expectations_json["expectations.json"]
    result(["Evaluation result"])

    begin_eval --> load_input
    load_input --> start_mode
    start_mode -->|fresh| fresh
    start_mode -->|continuation| continuation
    fresh --> protocol
    continuation --> protocol
    protocol -->|fixed-context| fixed_context
    protocol -->|tool-enabled| tool_enabled
    fixed_context --> budgets
    tool_enabled --> budgets
    budgets --> analyze
    analyze --> findings
    findings --> grader
    expectations_json -->|Private rubric| grader
    grader --> result

    classDef terminal fill:#334155,stroke:#334155,color:#ffffff
    classDef process fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef decision fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef agent fill:#dcfce7,stroke:#16a34a,color:#166534
    classDef private fill:#fee2e2,stroke:#dc2626,color:#991b1b

    class begin_eval,result terminal
    class load_input,fresh,continuation,fixed_context,tool_enabled,budgets process
    class start_mode,protocol decision
    class analyze,findings agent
    class grader,expectations_json private
```

## 3. Fresh vs. continuation — Two starting modes

```mermaid
flowchart TD
    subgraph fresh_review["FRESH REVIEW"]
        fresh_input["reviewer/input.json"]
        empty_conversation["Empty conversation"]
        no_inherited["No inherited actions"]
    end

    subgraph continuation_review["CONTINUATION REVIEW"]
        continuation_input["reviewer/input.json<br/>+ reviewer/prefix.json"]
        restore_history["Restore conversation history"]
        restore_tools["Restore previous tool calls<br/>and observations"]
        apply_budgets["Apply inherited usage<br/>and remaining budgets"]
        resume["Resume at checkpoint"]
    end

    begin_review(["Start reviewing"])

    fresh_input --> empty_conversation
    empty_conversation --> no_inherited
    no_inherited --> begin_review
    continuation_input --> restore_history
    restore_history --> restore_tools
    restore_tools --> apply_budgets
    apply_budgets --> resume
    resume --> begin_review

    classDef fresh fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef continuation fill:#f3e8ff,stroke:#9333ea,color:#6b21a8
    classDef complete fill:#dcfce7,stroke:#16a34a,color:#166534

    class fresh_input,empty_conversation,no_inherited fresh
    class continuation_input,restore_history,restore_tools,apply_budgets,resume continuation
    class begin_review complete
```

## 4. Real case walkthrough — `case-0003`

This diagram walks through the most instructive example: a code change, a
previously completed file read, and no remaining tool calls.

```mermaid
flowchart TD
    case_node["case-0003"]

    subgraph code_change["CODE CHANGE"]
        base_snapshot["Base snapshot: s-01<br/>return used #lt; limit"]
        head_snapshot["Head snapshot: s-02<br/>return used #lt;= limit"]
    end

    subgraph recorded_prefix["RECORDED PREFIX"]
        user_request["User requests code review"]
        agent_uses_tool["Agent calls shell tool"]
        read_file["Read src/quota.py at head"]
        tool_result["Tool returns file content<br/>51 bytes"]
        checkpoint["Checkpoint reached"]
    end

    subgraph remaining_budget["REMAINING BUDGET"]
        whole_path["Whole path: 1 tool call"]
        inherited["Inherited: 1 tool call"]
        remaining["Remaining: 0 tool calls"]
    end

    subgraph reviewer_continues["REVIEWER CONTINUES"]
        analyze["Analyze existing file content"]
        identify["Identify boundary-condition defect"]
        report["Report actionable finding"]
    end

    grader["Private grader checks<br/>finding-01<br/>src/quota.py, line 2"]

    case_node --> base_snapshot
    base_snapshot -->|One-line change| head_snapshot
    head_snapshot -->|Change under review| user_request
    user_request --> agent_uses_tool
    agent_uses_tool --> read_file
    read_file --> tool_result
    tool_result --> checkpoint
    checkpoint --> inherited
    whole_path --> remaining
    inherited --> remaining
    remaining -->|No additional tool calls| analyze
    analyze --> identify
    identify --> report
    report --> grader

    classDef code fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef history fill:#f3e8ff,stroke:#9333ea,color:#6b21a8
    classDef budget fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef review fill:#dcfce7,stroke:#16a34a,color:#166534
    classDef grader fill:#fee2e2,stroke:#dc2626,color:#991b1b

    class base_snapshot,head_snapshot code
    class user_request,agent_uses_tool,read_file,tool_result,checkpoint history
    class whole_path,inherited,remaining budget
    class analyze,identify,report review
    class grader grader
```

## 5. SHA-256 integrity — How documents are linked

```mermaid
flowchart LR
    source_file["Source file<br/>src/quota.py"]
    blob["Blob storage<br/>SHA-256 filename"]
    snapshot_entry["Snapshot file entry<br/>path + SHA-256"]
    prefix_json["prefix.json<br/>Exact bytes"]
    prefix_hash["start.prefix.sha256"]
    input_json["input.json<br/>Exact bytes"]
    input_hash["expectations.input_sha256"]
    expectations_json["expectations.json"]

    source_file -->|Hash content| blob
    blob -->|Referenced by hash| snapshot_entry
    snapshot_entry -->|Included in| input_json
    prefix_json -->|Hash exact bytes| prefix_hash
    prefix_hash -->|Stored in| input_json
    input_json -->|Hash exact bytes| input_hash
    input_hash -->|Stored in| expectations_json

    classDef source fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef hash fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef docs fill:#f3e8ff,stroke:#9333ea,color:#6b21a8
    classDef private fill:#fee2e2,stroke:#dc2626,color:#991b1b

    class source_file,blob source
    class snapshot_entry,prefix_hash,input_hash hash
    class prefix_json,input_json docs
    class expectations_json private
```

## 6. Expectations — What does the grader evaluate?

```mermaid
flowchart TD
    expectations_root["private/expectations.json"]
    dataset["Dataset metadata<br/>Labels, provenance, related cases"]
    evaluation["Evaluation expectations"]
    required_findings["Required findings"]
    non_findings["Non-findings"]
    retrieval["Retrieval requirements"]
    behavior["Review behavior"]
    continuation_rules["Continuation rules"]
    locations["Locations<br/>Base/head, path, lines"]
    evidence["Evidence<br/>Reproduction scenarios"]
    sources["Acceptable sources<br/>Snapshot + file"]
    remaining_actions["Required remaining actions"]
    forbidden_actions["Forbidden actions"]
    action_order["Essential action order"]
    grading["Private grading process"]

    expectations_root --> dataset
    expectations_root --> evaluation
    evaluation --> required_findings
    evaluation --> non_findings
    evaluation --> retrieval
    evaluation --> behavior
    evaluation --> continuation_rules
    required_findings --> locations
    required_findings --> evidence
    retrieval --> sources
    continuation_rules --> remaining_actions
    continuation_rules --> forbidden_actions
    continuation_rules --> action_order
    dataset --> grading
    evaluation --> grading

    classDef start_point fill:#334155,stroke:#334155,color:#ffffff
    classDef group fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    classDef detail fill:#f3e8ff,stroke:#9333ea,color:#6b21a8
    classDef grade fill:#dcfce7,stroke:#16a34a,color:#166534

    class expectations_root start_point
    class dataset,evaluation,required_findings,non_findings,retrieval,behavior,continuation_rules group
    class locations,evidence,sources,remaining_actions,forbidden_actions,action_order detail
    class grading grade
```

## Presenting the diagrams

For a live demo, present them in the order 1 → 2 → 4 → 3 → 5 → 6. That moves
from the overall architecture to a real example before introducing the more
technical aspects of the schemas.

To export SVG or PNG files for a presentation, paste each diagram into the
[Mermaid Live Editor](https://mermaid.live/).
