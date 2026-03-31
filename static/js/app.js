/**
 * Sheet Music Transposer – frontend logic
 *
 * Flow:
 *   1. User drags/selects a sheet-music image and chooses source/dest keys.
 *   2. On submit, image + keys are POSTed to /api/transpose.
 *   3. Server returns { original_abc, transposed_abc, source_key, dest_key }.
 *   4. abcjs renders both ABC strings into the notation panels.
 *   5. A download button lets the user save the transposed score as PNG.
 */

/* --------------------------------------------------------------------------
 * Constants
 * -------------------------------------------------------------------------- */
const API_URL = "/api/transpose";

/* --------------------------------------------------------------------------
 * DOM references (populated after DOMContentLoaded)
 * -------------------------------------------------------------------------- */
let dropZone, fileInput, previewImg, previewContainer, clearBtn;
let sourceKeySelect, destKeySelect;
let transposeBtn, downloadBtn;
let originalPanel, transposedPanel;
let originalLabel, transposedLabel;
let errorAlert, spinnerOverlay;

/* Holds the current image file */
let currentFile = null;

/* --------------------------------------------------------------------------
 * Initialise
 * -------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  dropZone          = document.getElementById("drop-zone");
  fileInput         = document.getElementById("file-input");
  previewImg        = document.getElementById("preview-img");
  previewContainer  = document.getElementById("preview-container");
  clearBtn          = document.getElementById("clear-btn");
  sourceKeySelect   = document.getElementById("source-key");
  destKeySelect     = document.getElementById("dest-key");
  transposeBtn      = document.getElementById("transpose-btn");
  downloadBtn       = document.getElementById("download-btn");
  originalPanel     = document.getElementById("original-panel");
  transposedPanel   = document.getElementById("transposed-panel");
  originalLabel     = document.getElementById("original-label");
  transposedLabel   = document.getElementById("transposed-label");
  errorAlert        = document.getElementById("error-alert");
  spinnerOverlay    = document.getElementById("spinner-overlay");

  /* Drop zone – click */
  dropZone.addEventListener("click", () => fileInput.click());

  /* Drop zone – drag events */
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  ["dragleave", "dragend"].forEach((ev) =>
    dropZone.addEventListener(ev, () => dropZone.classList.remove("drag-over"))
  );
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (files.length > 0) setFile(files[0]);
  });

  /* File input change */
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) setFile(fileInput.files[0]);
  });

  /* Clear button */
  clearBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearFile();
  });

  /* Form submit */
  transposeBtn.addEventListener("click", handleTranspose);

  /* Download button */
  downloadBtn.addEventListener("click", downloadTransposed);
});

/* --------------------------------------------------------------------------
 * File handling
 * -------------------------------------------------------------------------- */
function setFile(file) {
  const allowed = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  if (!allowed.includes(file.type)) {
    showError(`Unsupported file type: ${file.type}. Please upload a PNG, JPEG, GIF, or WebP image.`);
    return;
  }
  currentFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    previewContainer.classList.remove("d-none");
    dropZone.classList.add("d-none");
  };
  reader.readAsDataURL(file);
  hideError();
}

function clearFile() {
  currentFile = null;
  fileInput.value = "";
  previewImg.src = "";
  previewContainer.classList.add("d-none");
  dropZone.classList.remove("d-none");
  clearPanels();
  downloadBtn.classList.add("d-none");
}

/* --------------------------------------------------------------------------
 * Transpose
 * -------------------------------------------------------------------------- */
async function handleTranspose() {
  hideError();

  if (!currentFile) {
    showError("Please select a sheet music image first.");
    return;
  }

  const sourceKey = sourceKeySelect.value;
  const destKey   = destKeySelect.value;

  if (sourceKey === destKey) {
    showError("Source and destination keys are the same – nothing to transpose.");
    return;
  }

  const formData = new FormData();
  formData.append("image", currentFile);
  formData.append("source_key", sourceKey);
  formData.append("dest_key", destKey);

  showSpinner(true);
  transposeBtn.disabled = true;

  try {
    const resp = await fetch(API_URL, { method: "POST", body: formData });
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.error || `Server error: ${resp.status}`);
      return;
    }

    renderNotation(originalPanel,    data.original_abc);
    renderNotation(transposedPanel,  data.transposed_abc);

    originalLabel.textContent   = `Original (${data.source_key})`;
    transposedLabel.textContent = `Transposed (${data.dest_key})`;

    downloadBtn.classList.remove("d-none");

    /* Store transposed ABC for download */
    downloadBtn.dataset.abc = data.transposed_abc;
    downloadBtn.dataset.key = data.dest_key;

  } catch (err) {
    showError(`Network error: ${err.message}`);
  } finally {
    showSpinner(false);
    transposeBtn.disabled = false;
  }
}

/* --------------------------------------------------------------------------
 * abcjs rendering
 * -------------------------------------------------------------------------- */
function renderNotation(panel, abcString) {
  if (!abcString) {
    panel.innerHTML = "<em class='text-muted'>No notation available.</em>";
    return;
  }

  /* abcjs is loaded via CDN in the HTML template */
  if (typeof ABCJS === "undefined") {
    panel.innerHTML = `<pre class="small">${escapeHtml(abcString)}</pre>`;
    return;
  }

  panel.innerHTML = ""; // clear previous
  ABCJS.renderAbc(panel, abcString, {
    responsive: "resize",
    add_classes: true,
    paddingright: 0,
    paddingleft: 0,
  });
}

/* --------------------------------------------------------------------------
 * Download transposed score as PNG (via canvas)
 * -------------------------------------------------------------------------- */
function downloadTransposed() {
  const svg = transposedPanel.querySelector("svg");
  if (!svg) return;

  const svgData   = new XMLSerializer().serializeToString(svg);
  const svgBlob   = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl    = URL.createObjectURL(svgBlob);

  const img = new Image();
  img.onload = () => {
    const canvas  = document.createElement("canvas");
    const scale   = 2; // 2× for retina quality
    canvas.width  = img.width  * scale;
    canvas.height = img.height * scale;

    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);

    const destKey = (downloadBtn.dataset.key || "transposed")
      .replace(/\s+/g, "_");

    canvas.toBlob((blob) => {
      const a   = document.createElement("a");
      a.href    = URL.createObjectURL(blob);
      a.download = `transposed_${destKey}.png`;
      a.click();
      URL.revokeObjectURL(a.href);
    }, "image/png");

    URL.revokeObjectURL(svgUrl);
  };
  img.src = svgUrl;
}

/* --------------------------------------------------------------------------
 * UI helpers
 * -------------------------------------------------------------------------- */
function clearPanels() {
  originalPanel.innerHTML   = "";
  transposedPanel.innerHTML = "";
  originalLabel.textContent   = "Original";
  transposedLabel.textContent = "Transposed";
}

function showSpinner(visible) {
  spinnerOverlay.classList.toggle("active", visible);
}

function showError(msg) {
  errorAlert.textContent = msg;
  errorAlert.classList.remove("d-none");
}

function hideError() {
  errorAlert.classList.add("d-none");
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
