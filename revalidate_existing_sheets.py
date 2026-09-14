import sys
import logging
from datetime import datetime, date
from services.sheets_client import SheetsClient
from services.validator import validate_article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("revalidate_sheets")


def revalidate_existing_news_sheet():
    """
    Phase 5: One-off script to re-verify existing rows in 06_News_All sheet.
    Updates 'Review Status' column based on validator results without deleting any rows.
    """
    client = SheetsClient()
    if not client.is_connected() or not client.news_spreadsheet:
        logger.error("Could not connect to Google Sheets.")
        return

    try:
        wks = client.news_spreadsheet.worksheet(client.news_sheet_name)
        rows = wks.get_all_values()
        if len(rows) <= 1:
            logger.info("Sheet has no data rows to re-validate.")
            return

        header = rows[0]
        # Identify column indices (0-based)
        url_idx = 6      # 출처 URL
        media_idx = 5    # 출처 미디어명
        status_idx = 16  # Review Status

        # Find status index from header if possible
        for i, h in enumerate(header):
            if "url" in h.lower() and "출처" in h:
                url_idx = i
            elif "미디어" in h:
                media_idx = i
            elif "review" in h.lower() or "status" in h.lower():
                status_idx = i

        logger.info(f"Re-verifying {len(rows)-1} rows from sheet '{client.news_sheet_name}'...")

        seen_urls = set()
        cutoff_date = date(2026, 8, 15)  # Operational cutoff date

        summary_counts = {
            "Verified": 0,
            "Invalid": 0,
            "Archived": 0,
            "Duplicate": 0
        }

        # Update requests
        for row_num in range(2, len(rows) + 1):
            row = rows[row_num - 1]
            if len(row) <= url_idx:
                continue

            raw_url = row[url_idx].strip()
            media = row[media_idx].strip() if len(row) > media_idx else ""

            if not raw_url:
                new_status = "Invalid"
            else:
                v_res = validate_article(
                    url=raw_url,
                    source_media=media,
                    cutoff_date=cutoff_date,
                    existing_urls=seen_urls
                )

                if v_res["passed"]:
                    new_status = "Verified"
                    seen_urls.add(v_res["final_url"].lower())
                else:
                    reason = v_res["reason"]
                    if reason == "DUPLICATE":
                        new_status = "Duplicate"
                    elif reason == "TOO_OLD":
                        new_status = "Archived"
                    else:
                        new_status = "Invalid"

            summary_counts[new_status] = summary_counts.get(new_status, 0) + 1

            # Update Review Status column in Google Sheet
            try:
                wks.update_cell(row_num, status_idx + 1, new_status)
            except Exception as u_err:
                logger.warning(f"Failed updating row {row_num}: {u_err}")

        logger.info("=== Phase 5 Re-validation Complete ===")
        logger.info(f"Total Processed: {len(rows)-1} rows")
        for k, v in summary_counts.items():
            logger.info(f" - {k}: {v} rows")

    except Exception as e:
        logger.error(f"Error during sheet re-validation: {e}")


if __name__ == "__main__":
    revalidate_existing_news_sheet()
