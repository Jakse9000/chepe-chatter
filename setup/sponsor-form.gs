/**
 * Chepe Chatter — sponsor intake (Google Apps Script)
 * ---------------------------------------------------
 * This receives the "Advertise" form from the website and adds a row to your
 * Google Sheet. New rows arrive with approved = FALSE; you publish a sponsor
 * by changing that cell to TRUE. The site then shows it on the next build.
 *
 * SETUP (one time, ~5 minutes) — full steps are in the README:
 *   1. Create a Google Sheet. Name the first tab exactly:  Sponsors
 *   2. Put these headers in row 1 (one per column, A–I):
 *        timestamp | company | tagline_en | tagline_es | link | logo | section | email | approved
 *   3. Extensions → Apps Script. Delete any sample code, paste THIS file, Save.
 *   4. Deploy → New deployment → type "Web app".
 *        Execute as: Me      Who has access: Anyone
 *      Copy the Web app URL (ends in /exec).
 *   5. Share → Publish to web → choose the "Sponsors" sheet → CSV → Publish.
 *      Copy that CSV URL.
 *   6. Paste both URLs into feeds.yaml (sponsor_submit_url and sponsor_sheet_csv).
 */

// The exact Google Sheet this writes to (and that the website reads from).
// It's the ID in the sheet's URL: .../spreadsheets/d/THIS_PART/edit
var SHEET_ID = '18rCuY4kzkA3obDLZ24bPJrHRXbkJBeFHwyp4uoB3cK8';

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName('Sponsors');
    var p = (e && e.parameter) ? e.parameter : {};

    // Basic honeypot: ignore bots that fill the hidden "website" field.
    if (p.website) {
      return _json({ success: true });
    }

    sheet.appendRow([
      new Date(),
      _clean(p.company),
      _clean(p.tagline_en),
      _clean(p.tagline_es),
      _clean(p.link),
      _clean(p.logo),
      _clean(p.section),
      _clean(p.email),
      'FALSE'              // you flip this to TRUE to publish
    ]);

    // Optional: email yourself when a new request arrives.
    // MailApp.sendEmail('jaakse@gmail.com', 'New sponsor request', JSON.stringify(p));

    return _json({ success: true });
  } catch (err) {
    return _json({ success: false, error: String(err) });
  }
}

function _clean(v) {
  return (v == null ? '' : String(v)).slice(0, 500).trim();
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
