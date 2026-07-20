import glob
import json
import os
from typing import List

import pandas as pd
from dotenv import load_dotenv
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()


Gemini_API_Key = os.getenv("Gemini API Key")


class TransactionRow(BaseModel):
    timestamp: str = Field(
        description="The timestamp or date string. If a checkmark (✓) is present, write 'SAME_AS_ABOVE'"
    )
    pos_provider: str = Field(
        description="The POS Provider (e.g. Opay, Moniepoint, Palmpay). If (✓) is present, write 'SAME_AS_ABOVE'"
    )
    terminal_id: str = Field(
        description="The Terminal ID string. If (✓) is present, write 'SAME_AS_ABOVE'"
    )
    card_type: str = Field(
        description="The Card Type (Verve, Master, Visa). If (✓) is present, write 'SAME_AS_ABOVE'"
    )
    amount: str = Field(description="The numeric amount (e.g., '132,000' or '5,100')")
    off_status: str = Field(
        description="The status column ('Green', 'Green/✓', '✓'). If (✓) is present, write 'SAME_AS_ABOVE'"
    )
    response_code: str = Field(
        description="The response code (e.g. '00', '51', '91', 'PY'). If (✓) is present, write 'SAME_AS_ABOVE'"
    )
    ghost_debit: str = Field(
        description="The Ghost Debit boolean string ('True', 'False', 'true', 'false'). If (✓) is present, write 'SAME_AS_ABOVE'"
    )


class LedgerPage(BaseModel):
    transactions: List[TransactionRow]


def process_all_ledger_pages(data_folder_path: str, final_csv_path: str):
    image_extensions = ["*.png", "*.jpg", "*.jpeg", "*.PNG"]
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(data_folder_path, ext)))

    if not image_files:
        print(f"❌ Error: No images found in '{data_folder_path}'.")
        return

    print(f"📚 Found {len(image_files)} ledger pages to process.")
    all_pages_data = []

    prompt = """
    Convert this handwritten POS ledger sheet into a structured database list. 
    Map the columns carefully:
    - 'TIME STAMP' maps to 'timestamp'
    - 'POS PROVIDER' maps to 'pos_provider'
    - 'TERMINAL ID' maps to 'terminal_id'
    - 'CARD TYPE' maps to 'card_type'
    - 'AMT' maps to 'amount'
    - 'OFF STATUS' maps to 'off_status'
    - 'RESPONSE CODE' maps to 'response_code'
    - 'GHOST DEBIT' maps to 'ghost_debit'
    
    If any cell contains a checkmark (✓) meaning "same as above", write 'SAME_AS_ABOVE'.
    """

    for file_path in sorted(image_files):
        print(f"\nParsing page: {os.path.basename(file_path)}...")

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LedgerPage,
                    temperature=0.1,
                ),
            )

            raw_json = response.text
            parsed_data = json.loads(raw_json)

            transactions_list = parsed_data.get("transactions", [])
            page_df = pd.DataFrame(transactions_list)

            all_pages_data.append(page_df)
            print(f"✅ Successfully extracted {len(page_df)} rows from this page.")

        except Exception as e:
            print(f"❌ Failed to process {os.path.basename(file_path)}: {e}")
            continue

    if not all_pages_data:
        print("❌ No data was extracted.")
        return

    print("\nMerging all pages into a unified matrix...")
    master_df = pd.concat(all_pages_data, ignore_index=True)

    print("Executing look-up transformations and forward-filling empty rows...")
    master_df = master_df.replace("SAME_AS_ABOVE", pd.NA)

    columns_to_fill = [
        "timestamp",
        "pos_provider",
        "terminal_id",
        "card_type",
        "off_status",
        "response_code",
        "ghost_debit",
    ]
    master_df[columns_to_fill] = master_df[columns_to_fill].ffill()

    master_df.to_csv(final_csv_path, index=False)
    print(
        f"\n🚀 SUCCESS! All pages compiled. Master dataset saved to: {final_csv_path}"
    )
    print(f"📊 Total Rows Gathered: {len(master_df)}")


if __name__ == "__main__":
    process_all_ledger_pages("data", "pos_seed_data.csv")
