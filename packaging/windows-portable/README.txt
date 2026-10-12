VAI Local Evaluation - Portable Windows Package
================================================

Requirements:
- 64-bit Windows 10 or Windows 11
- Approximately 2 GB of free disk space
- No Docker, Python, Node.js, PostgreSQL, or administrator install is required

Start:
1. Extract the entire ZIP to a normal local folder.
2. Double-click "Start VAI.cmd".
3. The application opens at http://localhost:3000.

Stop:
- Double-click "Stop VAI.cmd" before moving or deleting the folder.

Data:
- Database and evidence files stay under the package's data folder.
- Logs stay under the logs folder.
- Do not expose ports 3000, 8000, or 55432 to an untrusted network.

This package is for trusted local QA and evaluation, not production deployment.
