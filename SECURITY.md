# Security Policy

## Supported versions

Until the first stable release is published, security fixes are applied to the latest code on the default branch. After releases begin, users should update to the newest available version before reporting a problem.

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue.

Use GitHub's private vulnerability reporting for this repository when it is available. If it is not available, open a public issue containing only a request for a private contact channel; do not include exploit details, private paths, task data, or screenshots with sensitive window titles.

A useful report includes:

- the affected commit or version;
- Windows and Python versions;
- impact and realistic attack conditions;
- minimal reproduction steps or a proof of concept;
- any suggested mitigation.

Particularly relevant areas include local task-data exposure, unsafe command invocation, window/process impersonation, privilege-boundary assumptions, and installer integrity.

Please allow time to reproduce and address a report before publishing details.
