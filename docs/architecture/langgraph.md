# LangGraph Workflow

```mermaid
stateDiagram-v2
    [*] --> Sales
    Sales --> Research: score and qualify
    Research --> EmailDraft: evidence and risks
    EmailDraft --> ApprovalGate: draft only
    ApprovalGate --> WaitingApproval: approval absent
    WaitingApproval --> Report: approved
    WaitingApproval --> Cancelled: rejected
    WaitingApproval --> EmailDraft: changes requested
    Report --> Completed: PDF-ready state

    Sales --> Failed: exception
    Research --> Failed: exception
    EmailDraft --> Failed: exception
    Report --> Failed: exception
    Failed --> ResumeNode: retry
    ResumeNode --> Research
    ResumeNode --> EmailDraft
    ResumeNode --> Report
```

Each node records duration, attempt, provider/model, token usage, cost, fallback history, evaluation, and audit evidence. Retry starts from the persisted `resume_node`.

Full design: [../langgraph-workflow.md](../langgraph-workflow.md).
