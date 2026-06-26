import streamlit as st
import pdfplumber
import re
from fpdf import FPDF
import io

# --- WEB APP INTERFACE ---
st.set_page_config(page_title="Lineup Automator", page_icon="📺", layout="wide")
st.title("📺 Local Lineups Automator")
st.write("Upload a Lineup Report (PDF) to automatically find missing CBS rows. The output PDF will retain all original schedule details.")

uploaded_file = st.file_uploader("Upload Lineup Report PDF", type="pdf")

if uploaded_file is not None:
    with st.spinner("Scanning document for exact row data..."):
        
        # --- THE EXTRACTION ENGINE ---
        full_text = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                # layout=True preserves the exact visual spacing of the columns
                full_text += page.extract_text(layout=True) + "\n"
                
        # --- THE LOGIC ---
        program_data = {}
        matches = list(re.finditer(r'\b(\d{6})\b', full_text))
        
        for i in range(len(matches)):
            current_code = matches[i].group(1)
            start_index = matches[i].start()
            
            # For the first chunk, we want to try and grab the Program Name which usually sits right before the group code
            # We'll step back about 25 characters on the same line to catch the name
            line_start = full_text.rfind('\n', 0, start_index)
            if line_start != -1:
                start_index = line_start + 1
                
            end_index = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
            
            # This 'chunk' now contains the exact text with all spacing from the original PDF
            chunk = full_text[start_index:end_index]
            
            is_wiat = bool(re.search(r'\bWIAT\b', chunk))
            is_cbs = False
            
            if not is_wiat and bool(re.search(r'\bCBS\b', chunk)):
                is_cbs = True
                
            if current_code not in program_data:
                program_data[current_code] = {"stations": set(), "raw_text": ""}
                
            if is_wiat or is_cbs:
                station = "WIAT" if is_wiat else "CBS"
                program_data[current_code]["stations"].add(station)
                # Save the raw text so we can print it exactly as-is later
                program_data[current_code]["raw_text"] += chunk
                
        # --- FIND ERRORS ---
        errors = []
        for code, data in program_data.items():
            if "WIAT" in data["stations"] and "CBS" not in data["stations"]:
                # We found an error! Save the exact text chunk
                errors.append(data["raw_text"])
                
        # --- GENERATE DETAILED PDF REPORT ---
        if errors:
            st.error(f"❌ FAILED: Found {len(errors)} erroneous programs. Generating detailed report...")
            
            # Create a Landscape PDF to fit all the columns
            pdf = FPDF(orientation='L', unit='mm', format='A4')
            pdf.add_page()
            
            # Title
            pdf.set_font("Courier", 'B', 14)
            pdf.cell(0, 10, txt="Lineup Scheduling Error Report (Missing CBS Rows)", ln=True, align='C')
            pdf.ln(5)
            
            # Table Header (Approximating the original PDF columns)
            pdf.set_font("Courier", 'B', 9)
            pdf.set_fill_color(200, 220, 255)
            header_text = "Program Name              Group Code Day Wks TC Start   End     Call Let T/Z  Work Unit"
            pdf.cell(0, 8, txt=header_text, ln=True, fill=True)
            
            # Print the exact rows
            pdf.set_font("Courier", '', 8)
            for error_chunk in errors:
                # Split the chunk into individual lines so FPDF can print them without breaking
                lines = error_chunk.split('\n')
                for line in lines:
                    if line.strip(): # Skip empty blank lines
                        # Replace special characters that might break FPDF
                        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
                        pdf.cell(0, 5, txt=clean_line, ln=True)
                
                # Add a divider line between different errors for readability
                pdf.line(10, pdf.get_y(), 287, pdf.get_y())
                pdf.ln(2)
                
            # Create a download button for the new PDF
            pdf_bytes = pdf.output(dest='S').encode('latin1')
            st.download_button(
                label="📥 Download Detailed Error Report (PDF)",
                data=pdf_bytes,
                file_name="Lineup_Detailed_Errors.pdf",
                mime="application/pdf"
            )
        else:
            st.success("✅ SUCCESS: No scheduling errors found in this PDF!")
            st.balloons()
