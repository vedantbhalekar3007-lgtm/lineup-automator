import streamlit as st
import pdfplumber
import re
from fpdf import FPDF
import io

# --- WEB APP INTERFACE ---
st.set_page_config(page_title="Lineup Automator", page_icon="📺")
st.title("📺 Local Lineups Automator")
st.write("Upload a Lineup Report (PDF) to automatically find missing CBS rows and generate an error report.")

uploaded_file = st.file_uploader("Upload Lineup Report PDF", type="pdf")

if uploaded_file is not None:
    with st.spinner("Scanning document..."):
        
        # --- THE EXTRACTION ENGINE ---
        full_text = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                full_text += page.extract_text(layout=True) + "\n"
                
        # --- THE LOGIC ---
        program_data = {}
        matches = list(re.finditer(r'\b(\d{6})\b', full_text))
        
        for i in range(len(matches)):
            current_code = matches[i].group(1)
            start_index = matches[i].start()
            end_index = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
            
            chunk = full_text[start_index:end_index]
            is_wiat = bool(re.search(r'\bWIAT\b', chunk))
            is_cbs = False
            
            if not is_wiat and bool(re.search(r'\bCBS\b', chunk)):
                is_cbs = True
                
            if is_wiat or is_cbs:
                station = "WIAT" if is_wiat else "CBS"
                if current_code not in program_data:
                    program_data[current_code] = set()
                program_data[current_code].add(station)
                
        # --- FIND ERRORS ---
        errors = []
        for code, stations in program_data.items():
            if "WIAT" in stations and "CBS" not in stations:
                errors.append({"Group Code": code, "Error Type": "Missing CBS Network"})
                
        # --- GENERATE PDF REPORT ---
        if errors:
            st.error(f"❌ FAILED: Found {len(errors)} erroneous rows.")
            
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt="Lineup Scheduling Error Report", ln=True, align='C')
            pdf.ln(10)
            
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(80, 10, "Group Code", border=1, fill=True, align='C')
            pdf.cell(100, 10, "Error Description", border=1, fill=True, align='C')
            pdf.ln()
            
            pdf.set_font("Arial", '', 12)
            for error in errors:
                pdf.cell(80, 10, str(error["Group Code"]), border=1, align='C')
                pdf.cell(100, 10, error["Error Type"], border=1, align='C')
                pdf.ln()
                
            # Create a download button for the new PDF
            pdf_bytes = pdf.output(dest='S').encode('latin1')
            st.download_button(
                label="📥 Download Error Report (PDF)",
                data=pdf_bytes,
                file_name="Lineup_Errors_Report.pdf",
                mime="application/pdf"
            )
        else:
            st.success("✅ SUCCESS: No scheduling errors found in this PDF!")
            st.balloons() # Adds a fun animation for the user