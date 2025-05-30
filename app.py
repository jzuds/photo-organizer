from flask import Flask, request, jsonify, render_template_string, session
import pandas as pd
import io
import os
import shutil

app = Flask(__name__)
app.secret_key = "replace_this_with_a_secure_random_key"

# 🔧 Change this to the base directory where you want to store copied files
PHOTO_PATH = "/home/zuds/projects/photo-organizer/test_output"  # << UPDATE THIS

@app.route('/')
def index():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>CSV Upload + Folder File Tree + Cross-Check</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; padding: 0 20px; color: #333; }
    h2 { border-bottom: 1px solid #ccc; padding-bottom: 5px; }
    #drop-area { border: 3px dashed #ccc; border-radius: 20px; padding: 20px; text-align: center; margin-bottom: 40px; color: #333; }
    #drop-area.highlight { border-color: purple; }
    #table-container { margin-top: 15px; font-size: 1.1em; }
    label.file-label { cursor: pointer; color: blue; text-decoration: underline; display: inline-block; margin-top: 10px; }
    #folder-section { margin-top: 40px; }
    input[type="text"] { padding: 8px; font-size: 16px; }
    #folderPath { width: 70%; }
    #copyFolder { width: 40%; margin-top: 10px; }
    button { padding: 8px 14px; font-size: 16px; margin-left: 10px; cursor: pointer; }
    #pathResult { margin-top: 20px; border: 1px solid #ccc; padding: 15px; border-radius: 8px; background: #f9f9f9; max-height: 600px; overflow-y: auto; }
    ul { padding-left: 1em; line-height: 1.5em; list-style-type: none; }
    li.folder > span { font-weight: bold; color: #0055aa; }
    li.file > span { color: #444; }
    .matched { color: green; font-weight: bold; }
    .missing { color: red; font-weight: bold; }
  </style>
</head>
<body>

  <h2>Upload CSV File</h2>
  <div id="drop-area">
    <h3>Drag & Drop your CSV file here</h3>
    <p>or click to select file</p>
    <input type="file" id="fileElem" accept=".csv" style="display:none" />
    <label for="fileElem" class="file-label">Select CSV File</label>
    <div id="table-container"></div>
  </div>

  <hr>

  <div id="folder-section">
    <h2>Enter Folder Path for Photo Search & Cross-Check with CSV</h2>
    <input type="text" id="folderPath" placeholder="Enter full folder path here..." value="{{ default_path }}" />
    <button id="checkBtn">Check Folder</button>
    
    <div style="margin-top: 20px;">
      <label for="copyFolder">Project Name:</label>
      <input type="text" id="copyFolder" placeholder="e.g. client_2025_photos" />
    </div>
    
    <button id="copyBtn" style="margin-top: 10px;" disabled>Copy Matched Files</button>
    <div id="pathResult"></div>
  </div>

<script>
  let lastCheckedPath = '';
  let lastMatchedFiles = [];

  const dropArea = document.getElementById('drop-area');
  const fileInput = document.getElementById('fileElem');
  const tableContainer = document.getElementById('table-container');

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, e => {
      e.preventDefault(); e.stopPropagation();
      dropArea.classList.toggle('highlight', eventName === 'dragenter' || eventName === 'dragover');
    });
  });

  dropArea.addEventListener('drop', handleDrop, false);
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) uploadFile(fileInput.files[0]);
  });

  function handleDrop(e) {
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  }

  function uploadFile(file) {
    if (!file.name.endsWith('.csv')) return alert('Please upload a valid CSV file.');
    const formData = new FormData();
    formData.append('file', file);
    fetch('/upload-csv', { method: 'POST', body: formData })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          tableContainer.innerHTML = '<p style="color:red;">' + data.error + '</p>';
        } else {
          tableContainer.innerHTML = `<p>File: <strong>${data.filename}</strong><br>
                                      Rows: <strong>${data.row_count}</strong><br>
                                      SPA entries: <strong>${data.spa_count}</strong></p>`;
        }
      })
      .catch(() => tableContainer.innerHTML = '<p style="color:red;">Upload failed.</p>');
  }

  document.getElementById('checkBtn').addEventListener('click', () => {
    const path = document.getElementById('folderPath').value.trim();
    const resultDiv = document.getElementById('pathResult');
    if (!path) return alert('Enter a folder path.');
    resultDiv.innerHTML = 'Checking folder...';

    fetch('/check-path', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ path })
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        resultDiv.innerHTML = '<p style="color:red;">' + data.error + '</p>';
        return;
      }
      lastCheckedPath = path;
      lastMatchedFiles = data.matched || [];
      document.getElementById('copyBtn').disabled = lastMatchedFiles.length === 0;

      let html = `<p><strong>${data.message}</strong></p>`;
      html += `<p>Matched: <strong>${data.matched.length}</strong>, Missing: <strong>${data.missing.length}</strong></p>`;

      if (data.missing.length > 0) {
        html += '<h3>Missing files:</h3><ul>' + data.missing.map(f => `<li class="missing">${f}</li>`).join('') + '</ul>';
      }

      if (data.matched.length > 0) {
        html += '<h3>Matched files:</h3><ul>' + data.matched.map(f => `<li class="matched">${f}</li>`).join('') + '</ul>';
      }

      resultDiv.innerHTML = html;
    });
  });

  document.getElementById('copyBtn').addEventListener('click', () => {
    const folderName = document.getElementById('copyFolder').value.trim();
    if (!lastCheckedPath || lastMatchedFiles.length === 0) return alert("No matched files.");
    if (!folderName) return alert("Enter a destination folder name.");
    if (!confirm(`Copy ${lastMatchedFiles.length} files into folder '${folderName}'?`)) return;

    const copyBtn = document.getElementById('copyBtn');
    copyBtn.disabled = true;
    copyBtn.textContent = 'Copying...';

    fetch('/copy-matched', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_path: lastCheckedPath,
        matched_files: lastMatchedFiles,
        folder_name: folderName
      })
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) alert('Error: ' + data.error);
      else alert(data.message);
    })
    .catch(() => alert('Server error during copy.'))
    .finally(() => {
      copyBtn.disabled = false;
      copyBtn.textContent = 'Copy Matched Files';
    });
  });
</script>

</body>
</html>
""", default_path=current_dir)

@app.route('/upload-csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify(error="No file uploaded."), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.csv'):
        return jsonify(error="Invalid file."), 400

    try:
        # Read CSV file into DataFrame
        stream = io.StringIO(file.stream.read().decode("UTF8"))
        df = pd.read_csv(stream)

        # Check for required columns
        required = {"SPA", "LASTNAME", "FIRSTNAME"}
        if not required.issubset(df.columns):
            missing = required - set(df.columns)
            return jsonify(error=f"Missing required columns: {', '.join(missing)}"), 400

        # Clean and store SPA column values
        spa_files = df['SPA'].dropna().astype(str).str.strip().tolist()

        # Store SPA list and full row data in session
        session['spa_files'] = spa_files
        session['spa_df'] = df.to_dict(orient='records')  # 👈 Used for filename prefixes

        return jsonify(
            filename=file.filename,
            row_count=len(df),
            spa_count=len(spa_files)
        )

    except Exception as e:
        return jsonify(error=f"Failed to process CSV: {str(e)}"), 400


@app.route('/check-path', methods=['POST'])
def check_path():
    data = request.get_json()
    path = data.get('path', '').strip()
    if not path or not os.path.isdir(path):
        return jsonify(error="Invalid directory."), 400
    spa_files = session.get('spa_files')
    if not spa_files:
        return jsonify(error="No SPA data loaded."), 400

    found_files = []
    for root, _, filenames in os.walk(path):
        for f in filenames:
            rel = os.path.relpath(os.path.join(root, f), path).replace("\\", "/")
            found_files.append(rel)
    found_names = set(os.path.basename(f) for f in found_files)
    spa_set = set(spa_files)
    matched = sorted(spa_set & found_names)
    missing = sorted(spa_set - found_names)

    return jsonify(message=f"Scanned directory: {path}", files=found_files,
                   spa_files=spa_files, matched=matched, missing=missing)

@app.route('/copy-matched', methods=['POST'])
def copy_matched():
    data = request.get_json()
    src_path = data.get('source_path', '').strip()
    matched = data.get('matched_files', [])
    folder_name = data.get('folder_name', '').strip()

    if not src_path or not matched or not folder_name:
        return jsonify(error="Missing data."), 400
    if not os.path.isdir(src_path):
        return jsonify(error="Source path invalid."), 400

    # Safe folder name
    safe_folder = "".join(c for c in folder_name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_folder:
        return jsonify(error="Invalid folder name."), 400

    dest_dir = os.path.join(PHOTO_PATH, safe_folder)
    os.makedirs(dest_dir, exist_ok=True)

    # Load mapping from SPA filename -> LASTNAME_FIRSTNAME
    spa_df = session.get('spa_df')
    if not spa_df:
        return jsonify(error="Original CSV data not found in session."), 400

    mapping = {}
    for row in spa_df:
        spa = row.get("SPA", "").strip()
        if spa:
            lastname = row.get("LASTNAME", "").strip()
            firstname = row.get("FIRSTNAME", "").strip()
            mapping[spa] = f"{lastname}_{firstname}"

    copied, errors = [], []
    for f in matched:
        base_name = os.path.basename(f)
        prefix = mapping.get(base_name, "UNKNOWN")
        new_name = f"{prefix}_{base_name}"
        found = False
        for root, _, files in os.walk(src_path):
            if base_name in files:
                try:
                    shutil.copy2(os.path.join(root, base_name), os.path.join(dest_dir, new_name))
                    copied.append(new_name)
                except Exception as e:
                    errors.append(f"Error copying {base_name}: {e}")
                found = True
                break
        if not found:
            errors.append(f"{base_name} not found.")

    if errors:
        return jsonify(error="; ".join(errors)), 500
    return jsonify(message=f"Copied {len(copied)} file(s) to {dest_dir}.")

if __name__ == '__main__':
    app.run(debug=True)
