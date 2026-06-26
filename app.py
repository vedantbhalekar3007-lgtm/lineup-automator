import streamlit as st
import pdfplumber
import re
from fpdf import FPDF

# --- WEB APP INTERFACE ---
st.set_page_config(page_title="Lineup Automator", page_icon="📺")
st.title("📺 Local Lineups Automator")
st.write("Upload a Lineup Report (PDF) to automatically find missing CBS rows. The output PDF will only include Program Name, Day, Wks, and Call Letter.")

uploaded_file = st.file_uploader("Upload Lineup Report PDF", type="pdf")

if uploaded_file is not None:
    with st.spinner("Extracting specific columns..."):
        
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
            
            # Get the chunk of text for this program
            line_start = full_text.rfind('\n', 0, matches[i].start())
            start_index = line_start + 1 if line_start != -1 else matches[i].start()
            end_index = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
            
            chunk = full_text[start_index:end_index]
            
            is_wiat = bool(re.search(r'\bWIAT\b', chunk))
            is_cbs = False
            if not is_wiat and bool(re.search(r'\bCBS\b', chunk)):
                is_cbs = True
                
            if current_code not in program_data:
                program_data[current_code] = {
                    "stations": set(), 
                    "program_name": "", 
                    "day": "", 
                    "wks": "", 
                    "call_let": ""
                }
                
            # Extract the specific 4 columns we want from the line
            for line in chunk.split('\n'):
                if current_code in line:
                    # Looks for: (Program Name) (Code) (Day) (Wks)
                    m = re.search(rf'(.*?)\s*{current_code}\s+([A-Z]{{3}})\s+(\d+)', line)
                    if m:
                        p_name = m.group(1).strip()
                        # Clean up asterisks if they exist in the original PDF
                        p_name = p_name.replace('*', '').strip() 
                        
                        if p_name and not program_data[current_code]["program_name"]:
                            program_data[current_code]["program_name"] = p_name
                        
                        program_data[current_code]["day"] = m.group(2)
                        program_data[current_code]["wks"] = m.group(3)
                        
            if is_wiat or is_cbs:
                station = "WIAT" if is_wiat else "CBS"
                program_data[current_code]["stations"].add(station)
                if station == "WIAT":
                    program_data[current_code]["call_let"] = "WIAT"
                
        # --- FIND ERRORS ---
        errors = []
        for code, data in program_data.items():
            if "WIAT" in data["stations"] and "CBS" not in data["stations"]:
                errors.append(data)
                
        # --- GENERATE DETAILED PDF REPORT ---
        if errors:
            st.error(f"❌ FAILED: Found {len(errors)} erroneous programs.")
            
            # Create a standard Portrait PDF
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()
            
            # Title
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt="Lineup Scheduling Error Report", ln=True, align='C')
            pdf.ln(8)
            
            # Table Header
            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(200, 220, 255)
            
            # Set column widths perfectly
            col_name = 85
            col_day = 30
            col_wks = 30
            col_call = 40
            
            pdf.cell(col_name, 10, "Program Name", border=1, fill=True, align='C')
            pdf.cell(col_day, 10, "Day", border=1, fill=True, align='C')
            pdf.cell(col_wks, 10, "Wks", border=1, fill=True, align='C')
            pdf.cell(col_call, 10, "Call Letter", border=1, fill=True, align='C')
            pdf.ln()
            
            # Table Rows
            pdf.set_font("Arial", '', 11)
            for err in errors:
                # Fallback text if a name is completely blank in the PDF
                name_text = err["program_name"] if err["program_name"] else "Unknown Program"
                
                pdf.cell(col_name, 10, name_text, border=1, align='C')
                pdf.cell(col_day, 10, err["day"], border=1, align='C')
                pdf.cell(col_wks, 10, err["wks"], border=1, align='C')
                pdf.cell(col_call, 10, err["call_let"], border=1, align='C')
                pdf.ln()
                
            # Create a download button
            pdf_bytes = pdf.output(dest='S').encode('latin1')
            st.download_button(
                label="📥 Download Error Report (PDF)",
                data=pdf_bytes,
                file_name="Lineup_Missing_CBS_Report.pdf",
                mime="application/pdf"
            )
        else:
            st.success("✅ SUCCESS: No scheduling errors found in this PDF!")
            st.balloons()
