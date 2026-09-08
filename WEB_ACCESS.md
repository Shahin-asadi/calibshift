# Web access and launch — CalibShift

The interactive interface is a Streamlit app. It runs in a web browser while a Python process performs the analysis. The repository supplies that app, examples, reports and automated checks. A public application server has not been deployed.

| What you open | What it provides |
|---|---|
| This GitHub repository | Source code, documentation and downloadable examples. |
| `START_WINDOWS.cmd`, then the printed local URL | The working interactive app on your computer. |
| [Example PDF](benchmarks/reference_run/temperature_transfer/summary.pdf) | An actual computed report you can read without installing Python. |
| [GitHub Actions](https://github.com/Shahin-asadi/calibshift/actions/workflows/tests.yml) | Temporary jobs that test and build the software; they stop after completing. |
| A future hosted Streamlit URL | An interactive app on a server, requiring a separate owner-managed deployment. No such URL is configured here. |

## Run the app on your computer

1. [Download the complete repository ZIP](https://github.com/Shahin-asadi/calibshift/archive/refs/heads/main.zip), then **Extract All**. Keep `.github`, `.streamlit`, `src` and the other folders together. A download button retrieves files; it cannot install or execute Python from the GitHub page.
2. Install Python **3.12 or 3.14** if needed. Double-click `START_WINDOWS.cmd` inside the extracted repository. First-time setup needs internet access and creates a project-local `.venv`.
3. Keep the launcher window open. Use the URL printed there, normally **http://127.0.0.1:8501**. If a browser tab does not open automatically, paste that address into Chrome. The address works only while the app is running on that computer.
4. Choose **Bundled example**, click **3. Run analysis**, then read the overview and download HTML, PDF or the extended ZIP. For your measurements, use CSV, XLSX or paste and follow [Input guide](INPUT_GUIDE.md).
5. Close the launcher with **Ctrl+C** when finished. If port 8501 is already used by another tool, open PowerShell in this repository and use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\launch.ps1 -Port 8502
```

Then open the address printed for port 8502. Use a different free port for every tool running at the same time. Each repository has its own environment.

To read the HTML example without Python, open `benchmarks/reference_run/temperature_transfer/summary.html` from the extracted ZIP. GitHub's ordinary file view displays HTML source rather than serving it as an application.

## Interactive online deployment — owner steps

Use a direct **Streamlit Community Cloud** app URL in the README and the GitHub Website field after deployment. The existing scientific-checks workflow tests the code; hosting is configured in Streamlit.

Local hosting preparation includes runtime-only `requirements.txt` using `constraints.txt`, the existing `app.py` entrypoint, a 50 MB upload limit, disabled Streamlit usage statistics, and an interface notice explaining server processing. This does not create a public URL or establish hosted performance.

When you are ready to publish these local changes:

1. Commit and push them yourself. Wait for **scientific-checks** to pass on that new commit.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in as the account authorized to manage this repository. Connecting the service is a separate owner action.
3. Select **Create app**, then repository **`Shahin-asadi/calibshift`**, branch **`main`**, and main file **`app.py`**. In advanced settings choose **Python 3.12** if offered, matching the recorded CI major/minor route. Do not rely on an unverified default Python version. No app secret or AI API key is needed.
4. Deploy and wait for the dependency installation and app startup. Copy the actual URL supplied by Streamlit; a particular subdomain is not assumed to be available.
5. On that real URL, run a bundled example, upload a small public CSV, check XLSX/paste, then download HTML/PDF/ZIP. Check a second browser session independently and inspect the server logs for errors. Hosted resource limits, uptime, concurrency and server font rendering remain unverified until these checks run there.
6. After those checks pass, add that URL to GitHub's **About → Website** and add a **Live app** link to the README. The current README deliberately has no invented online address.

Use public example measurements for the online demonstration. Uploads to a hosted app are processed by the hosting server; use the local installation for confidential measurements. The application does not require an AI service. Read the hosting provider's current data and account terms before offering a public upload service.

If deploying all four, create four separate Streamlit apps from their respective repositories. The scientific code and ownership stay independent.

Official instructions: [deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [dependency files](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

The added `workflow_dispatch` trigger allows manual scientific checks once pushed to the default branch. It does not deploy. [Manual workflow instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

## What the owner does next

Review these local documentation/workflow changes, then commit and push them when ready. Deploy the selected Streamlit app and check its actual URL before adding the Website link. Keep the Website field empty until that URL works. No PR, commit, push, release, deployment or repository setting was made by this local documentation update.
