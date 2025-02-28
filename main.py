import streamlit as st
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
import pandas as pd
import json
import re
from io import BytesIO

def extract_tables_from_pdf(pdf_file):
    try:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        # Convert uploaded file to path-compatible format
        result = converter.convert(pdf_file)

        all_tables = {
            "number_of_tables": len(result.document.tables),
            "tables": []
        }

        for table_index, table in enumerate(result.document.tables):
            try:
                table_df = table.export_to_dataframe()
                table_info = {
                    "table_number": table_index + 1,
                    "columns": list(table_df.columns),
                    "row_count": len(table_df),
                    "data": table_df.to_dict('records'),
                    "location": {
                        "page": table.page_number if hasattr(table, 'page_number') else None,
                        "coordinates": table.coordinates if hasattr(table, 'coordinates') else None
                    }
                }
                numeric_columns = table_df.select_dtypes(include=['number']).columns
                if len(numeric_columns) > 0:
                    table_info["numerical_summary"] = table_df[numeric_columns].describe().to_dict()
                all_tables["tables"].append(table_info)

            except Exception as e:
                st.error(f"Error processing table {table_index + 1}: {str(e)}")
                continue

        return all_tables

    except Exception as e:
        return {
            "error": f"Error processing PDF: {str(e)}",
            "number_of_tables": 0,
            "tables": []
        }

def process_transactions(tables_data):
    records = []
    pattern = re.compile(r'(\d{2}/\d{2}/\d{2})\s+(\d{2}/\d{2}/\d{2})\s+(\w+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})(?:Dr|Cr)')

    for table in tables_data.get('tables', []):
        for row in table.get('data', []):
            row_text = " ".join(val for val in row.values() if isinstance(val, str) and val.strip())
            if not row_text:
                continue

            for m in pattern.finditer(row_text):
                post_date = m.group(1)
                value_date = m.group(2)
                tran_type = m.group(3).upper()
                amount = m.group(4).replace(',', '')
                balance = m.group(5).replace(',', '')

                debit = amount if tran_type == "DEBIT" else ""
                credit = amount if tran_type == "CREDIT" else ""

                rec = {
                    'Post Date': post_date,
                    'Value Date': value_date,
                    'Details': tran_type,
                    'Debit': debit,
                    'Credit': credit,
                    'Balance': balance
                }
                records.append(rec)

    return pd.DataFrame(records)

def main():
    st.title("PDF Transaction Extractor")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")
    
    if uploaded_file is not None:
        # Process the PDF
        with st.spinner("Processing PDF..."):
            tables_data = extract_tables_from_pdf(uploaded_file)
            
            if tables_data["number_of_tables"] > 0:
                df = process_transactions(tables_data)
                
                # Display results
                st.write(f"Found {tables_data['number_of_tables']} tables")
                st.dataframe(df)
                
                # Save to CSV button
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name="transactions.csv",
                    mime="text/csv"
                )
                
                # Save to Excel button
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False)
                st.download_button(
                    label="Download as Excel",
                    data=excel_buffer.getvalue(),
                    file_name="transactions.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.error("No tables found in the PDF or error occurred during processing")
                if "error" in tables_data:
                    st.error(tables_data["error"])

if __name__ == "__main__":
    main()
