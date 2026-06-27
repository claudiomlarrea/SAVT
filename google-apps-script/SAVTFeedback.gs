/**
 * SAVT — Valoraciones de usuarios → Google Sheets
 *
 * 1. Crear una planilla en Google Sheets (ej. "SAVT Feedback").
 * 2. Extensiones → Apps Script → pegar este archivo → guardar.
 * 3. Reemplazar SPREADSHEET_ID por el ID de la planilla.
 * 4. (Opcional) Definir FEEDBACK_TOKEN y el mismo valor en Streamlit secrets.
 * 5. Implementar → Nueva implementación → Aplicación web
 *    - Ejecutar como: Yo
 *    - Quién tiene acceso: Cualquier persona
 * 6. Copiar la URL de la app web en Streamlit secrets:
 *    [feedback]
 *    submit_url = "https://script.google.com/macros/s/.../exec"
 *    token = "su-token-secreto"
 */

var SPREADSHEET_ID = "REEMPLAZAR_POR_ID_DE_PLANILLA";
var SHEET_NAME = "Feedback";
var FEEDBACK_TOKEN = ""; // opcional; vacío = sin token

var HEADERS = [
  "timestamp",
  "rating",
  "comment",
  "version",
  "filename",
  "icai",
  "profile",
  "source",
];

function doGet() {
  return json_({ ok: true, service: "savt-feedback" });
}

function doPost(e) {
  try {
    var payload = parsePayload_(e);
    if (!payload) {
      return json_({ ok: false, error: "empty_payload" });
    }

    if (FEEDBACK_TOKEN && payload.token !== FEEDBACK_TOKEN) {
      return json_({ ok: false, error: "unauthorized" });
    }

    var sheet = getOrCreateSheet_();
    sheet.appendRow([
      payload.timestamp || new Date().toISOString(),
      payload.rating || "",
      payload.comment || "",
      payload.version || "",
      payload.filename || "",
      payload.icai || "",
      payload.profile || "",
      payload.source || "savt-streamlit",
    ]);

    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function getOrCreateSheet_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function parsePayload_(e) {
  if (!e || !e.postData || !e.postData.contents) {
    return null;
  }
  try {
    return JSON.parse(e.postData.contents);
  } catch (err) {
    return null;
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
