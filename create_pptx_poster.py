import os
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def build_poster():
    prs = Presentation()
    # Standard Academic Poster size: 36 inches wide by 48 inches high
    prs.slide_width = Inches(36)
    prs.slide_height = Inches(48)

    blank_layout = prs.slide_layouts[6] # blank slide
    slide = prs.slides.add_slide(blank_layout)

    # Color Palette
    DARK_NAVY = RGBColor(10, 25, 47)       # #0a192f
    HEADER_BLUE = RGBColor(13, 33, 61)     # #0d213d
    GOLD = RGBColor(245, 158, 11)          # #f59e0b
    EMERALD = RGBColor(16, 185, 129)       # #10b981
    CORAL = RGBColor(249, 115, 22)         # #f97316
    LIGHT_BG = RGBColor(248, 250, 252)     # #f8fafc
    WHITE = RGBColor(255, 255, 255)
    CARD_BG = RGBColor(255, 255, 255)
    CARD_HEADER_BG = RGBColor(241, 245, 249) # #f1f5f9
    BORDER_COLOR = RGBColor(203, 213, 225) # #cbd5e1
    TEXT_DARK = RGBColor(15, 23, 42)       # #0f172a
    TEXT_MUTED = RGBColor(71, 85, 105)     # #475569
    CYAN_ACCENT = RGBColor(56, 189, 248)   # #38bdf8

    # Set background
    bg_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(36), Inches(48))
    bg_shape.fill.solid()
    bg_shape.fill.fore_color.rgb = LIGHT_BG
    bg_shape.line.fill.background()

    # ==========================================
    # 1. HEADER SECTION (Height: 6.0 inches)
    # ==========================================
    header_box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(36), Inches(6.0))
    header_box.fill.solid()
    header_box.fill.fore_color.rgb = HEADER_BLUE
    header_box.line.fill.background()

    # Gold decorative strip
    gold_strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(6.0), Inches(36), Inches(0.15))
    gold_strip.fill.solid()
    gold_strip.fill.fore_color.rgb = GOLD
    gold_strip.line.fill.background()

    # MITS Round Logo badge
    logo_badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.2), Inches(0.4), Inches(1.8), Inches(1.8))
    logo_badge.fill.solid()
    logo_badge.fill.fore_color.rgb = WHITE
    logo_badge.line.color.rgb = GOLD
    logo_badge.line.width = Pt(4)
    tf_logo = logo_badge.text_frame
    tf_logo.word_wrap = True
    p = tf_logo.paragraphs[0]
    p.text = "MITS"
    p.font.bold = True
    p.font.size = Pt(28)
    p.font.color.rgb = DARK_NAVY
    p.alignment = PP_ALIGN.CENTER
    p2 = tf_logo.add_paragraph()
    p2.text = "GWALIOR"
    p2.font.bold = True
    p2.font.size = Pt(12)
    p2.font.color.rgb = TEXT_MUTED
    p2.alignment = PP_ALIGN.CENTER

    # Event Crest on right
    event_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(27.8), Inches(0.4), Inches(7.0), Inches(1.8))
    event_box.fill.solid()
    event_box.fill.fore_color.rgb = DARK_NAVY
    event_box.line.color.rgb = EMERALD
    event_box.line.width = Pt(2)
    tf_ev = event_box.text_frame
    tf_ev.word_wrap = True
    p = tf_ev.paragraphs[0]
    p.text = "GWALIOR VIGYAN MAHOTSAV 2026"
    p.font.bold = True
    p.font.size = Pt(19)
    p.font.color.rgb = EMERALD
    p.alignment = PP_ALIGN.CENTER
    p2 = tf_ev.add_paragraph()
    p2.text = "ABV-IIITM Gwalior · Vigyan Bharati"
    p2.font.size = Pt(15)
    p2.font.color.rgb = WHITE
    p2.alignment = PP_ALIGN.CENTER

    # Institutional Text (Center)
    inst_tx = slide.shapes.add_textbox(Inches(3.4), Inches(0.25), Inches(24.0), Inches(1.8))
    tf_inst = inst_tx.text_frame
    tf_inst.word_wrap = True
    p = tf_inst.paragraphs[0]
    p.text = "माधव प्रौद्योगिकी एवं विज्ञान संस्थान, ग्वालियर (म.प्र.), भारत"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER
    p2 = tf_inst.add_paragraph()
    p2.text = "MADHAV INSTITUTE OF TECHNOLOGY & SCIENCE, GWALIOR (M.P.), INDIA"
    p2.font.size = Pt(25)
    p2.font.bold = True
    p2.font.color.rgb = WHITE
    p2.alignment = PP_ALIGN.CENTER
    p3 = tf_inst.add_paragraph()
    p3.text = "(Deemed to be University · Declared under Distinct Category by Ministry of Education, Govt. of India) · NAAC A++ GRADE"
    p3.font.size = Pt(14)
    p3.font.color.rgb = GOLD
    p3.alignment = PP_ALIGN.CENTER

    # Main Project Title
    title_tx = slide.shapes.add_textbox(Inches(1.0), Inches(2.3), Inches(34.0), Inches(1.6))
    tf_title = title_tx.text_frame
    tf_title.word_wrap = True
    p = tf_title.paragraphs[0]
    p.text = "AI-POWERED FITNESS ASSESSMENT PLATFORM"
    p.font.size = Pt(46)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER
    p2 = tf_title.add_paragraph()
    p2.text = "Real-Time Movement Analysis and Automated Fitness Assessment using Computer Vision"
    p2.font.size = Pt(24)
    p2.font.bold = True
    p2.font.color.rgb = CYAN_ACCENT
    p2.alignment = PP_ALIGN.CENTER

    # Presenters & Dept Bar
    pres_bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(4.3), Inches(33.6), Inches(1.3))
    pres_bar.fill.solid()
    pres_bar.fill.fore_color.rgb = DARK_NAVY
    pres_bar.line.color.rgb = BORDER_COLOR
    pres_bar.line.width = Pt(1)
    tf_pres = pres_bar.text_frame
    tf_pres.word_wrap = True
    p = tf_pres.paragraphs[0]
    p.text = "Presented by: Aakanksha Vidushi Pandey (BTAI21O1001) & Dhruv Urmaliya (BTAI21O1042)"
    p.font.size = Pt(21)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER
    p2 = tf_pres.add_paragraph()
    p2.text = "Under the Guidance of: Dr. Neelam Arya · Centre for Artificial Intelligence, MITS Gwalior"
    p2.font.size = Pt(17)
    p2.font.color.rgb = GOLD
    p2.alignment = PP_ALIGN.CENTER

    # Helper function to create cards
    def add_card(x, y, w, h, title):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BORDER_COLOR
        card.line.width = Pt(1.5)

        header = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.9))
        header.fill.solid()
        header.fill.fore_color.rgb = CARD_HEADER_BG
        header.line.color.rgb = BORDER_COLOR
        header.line.width = Pt(1)
        tf = header.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"  {title.upper()}"
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = DARK_NAVY
        p.alignment = PP_ALIGN.LEFT
        return card

    # ==========================================
    # 2. ROW 1: INTRODUCTION & PROBLEM STATEMENT
    # Y: 6.5 to 11.2 (Height: 4.6 inches)
    # ==========================================
    add_card(1.2, 6.5, 16.5, 4.6, "01 — Introduction & Overview")
    tx_intro = slide.shapes.add_textbox(Inches(1.5), Inches(7.5), Inches(15.9), Inches(3.4))
    tf_in = tx_intro.text_frame
    tf_in.word_wrap = True
    p = tf_in.paragraphs[0]
    p.text = "The AI-Powered Fitness Assessment Platform is an automated, computer-vision system designed to assist athletic trainers, academies, and coaches in conducting objective physical evaluations."
    p.font.size = Pt(16)
    p.font.color.rgb = TEXT_DARK
    
    bullets = [
        "Replaces subjective human counting with real-time YOLO26-Pose estimation.",
        "Extracts 17 full-body keypoints from a standard webcam video feed (4 FPS / 250ms).",
        "Calculates joint angles and spatial displacement via vector dot product mathematics.",
        "Combines real-time movement tracking with multi-athlete management and digital records."
    ]
    for b in bullets:
        p = tf_in.add_paragraph()
        p.text = f"•  {b}"
        p.font.size = Pt(15)
        p.font.color.rgb = TEXT_MUTED

    add_card(18.3, 6.5, 16.5, 4.6, "02 — Problem Statement & Motivation")
    tx_prob = slide.shapes.add_textbox(Inches(18.6), Inches(7.5), Inches(15.9), Inches(3.4))
    tf_pr = tx_prob.text_frame
    tf_pr.word_wrap = True
    p = tf_pr.paragraphs[0]
    p.text = "Traditional physical fitness testing in sporting academies, schools, and armed forces relies on manual stopwatches, visual counting, and paper scorecards."
    p.font.size = Pt(16)
    p.font.color.rgb = TEXT_DARK
    
    p_bullets = [
        "Subjective Observation Bias: Human fatigue leads to missed repetitions and inconsistent judging.",
        "No Angle Verification: Incomplete movement (e.g. shallow sit-ups) is falsely counted as valid reps.",
        "Data Fragmentation: Paper-based records make longitudinal tracking and cohort comparison slow.",
        "High Equipment Cost: High-end optical motion capture labs are unaffordable for grassroots centres."
    ]
    for b in p_bullets:
        p = tf_pr.add_paragraph()
        p.text = f"•  {b}"
        p.font.size = Pt(15)
        p.font.color.rgb = TEXT_MUTED

    # ==========================================
    # 3. ROW 2: THE 8-STEP OPERATIONAL WORKFLOW
    # (Centerpiece - Height: 10.2 inches, Y: 11.4)
    # ==========================================
    wf_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(11.4), Inches(33.6), Inches(10.2))
    wf_card.fill.solid()
    wf_card.fill.fore_color.rgb = WHITE
    wf_card.line.color.rgb = RGBColor(2, 132, 199)
    wf_card.line.width = Pt(3)

    wf_header = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(11.4), Inches(33.6), Inches(1.0))
    wf_header.fill.solid()
    wf_header.fill.fore_color.rgb = RGBColor(2, 132, 199)
    wf_header.line.fill.background()
    p = wf_header.text_frame.paragraphs[0]
    p.text = " ⭐ END-TO-END SYSTEM WORKFLOW (THE 8-STEP OPERATIONAL PIPELINE)"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER

    steps_data = [
        ("01", "Trainer Sign In", "Secure login with credentials/OAuth. Enforces strict multi-trainer data isolation (trainer=request.user).", 1.6, 12.7),
        ("02", "Athlete Selection", "Trainer registers a new athlete or selects an existing profile with sport, age, height, and weight baseline.", 9.8, 12.7),
        ("03", "Exercise Selection", "Trainer chooses one of the 8 physical fitness tests (Vertical Jump, Broad Jump, Sit-ups, Sprint, etc.).", 18.0, 12.7),
        ("04", "Movement Capture", "Standard webcam captures video frames at 4 FPS (250ms interval) balancing responsiveness with CPU load.", 26.2, 12.7),
        ("05", "Pose Detection", "YOLO26-Pose extracts 17 body keypoints (shoulders, elbows, wrists, hips, knees, ankles) with confidence > 0.5.", 1.6, 16.7),
        ("06", "Movement Analysis", "Vector dot product computes joint angles. Dual-threshold state machine verifies reps and displacements.", 9.8, 16.7),
        ("07", "Real-Time Results", "Canvas displays skeleton overlay, live joint angles, completed repetitions, peak metrics & score (0-100).", 18.0, 16.7),
        ("08", "Save & Review", "Completed assessment persisted to SQLite/PostgreSQL. Instant updates to athlete history, charts & team analytics.", 26.2, 16.7),
    ]

    for num, name, desc, sx, sy in steps_data:
        tile = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(sx), Inches(sy), Inches(7.8), Inches(3.6))
        tile.fill.solid()
        tile.fill.fore_color.rgb = RGBColor(240, 249, 255) if int(num) <= 4 else (RGBColor(236, 253, 245) if int(num) <= 6 else RGBColor(255, 247, 237))
        tile.line.color.rgb = RGBColor(2, 132, 199) if int(num) <= 4 else (EMERALD if int(num) <= 6 else CORAL)
        tile.line.width = Pt(2)
        
        tf = tile.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"STEP {num} — {name.upper()}"
        p.font.size = Pt(17)
        p.font.bold = True
        p.font.color.rgb = DARK_NAVY
        p.alignment = PP_ALIGN.LEFT
        
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(14)
        p2.font.color.rgb = TEXT_DARK
        p2.alignment = PP_ALIGN.LEFT

    # ==========================================
    # 4. ROW 3: EIGHT EXERCISE MODULES & BIOMECHANICAL AI
    # Y: 21.9 to 30.2 (Height: 8.3 inches)
    # ==========================================
    add_card(1.2, 21.9, 18.0, 8.3, "03 — Eight Fitness Exercise Modules")
    ex_list = [
        ("Vertical Jump", "Ankle Y-displacement from standing baseline (cm)"),
        ("Broad Jump", "Takeoff-to-landing ankle X-displacement (cm)"),
        ("Sit-ups", "Hip angle (Shoulder-Hip-Knee); full UP/DOWN cycles"),
        ("Sit & Reach", "Maximum forward wrist reach past toe baseline (cm)"),
        ("Sprint Test", "Line crossing detection & precision digital stopwatch (sec)"),
        ("Medicine Ball Throw", "Upper-body power via wrist release proxy tracking (cm)"),
        ("Shuttle Run", "Directional agility boundary crossings via hip position"),
        ("Endurance Run", "Stamina cadence monitoring through completed laps")
    ]
    
    for idx, (ex_name, ex_desc) in enumerate(ex_list):
        col = idx % 2
        row = idx // 2
        ex_x = 1.6 + col * 8.6
        ex_y = 23.0 + row * 1.65
        
        ex_tile = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(ex_x), Inches(ex_y), Inches(8.3), Inches(1.45))
        ex_tile.fill.solid()
        ex_tile.fill.fore_color.rgb = CARD_HEADER_BG
        ex_tile.line.color.rgb = BORDER_COLOR
        ex_tile.line.width = Pt(1)
        tf = ex_tile.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"✔ {ex_name}"
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = DARK_NAVY
        p2 = tf.add_paragraph()
        p2.text = ex_desc
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_MUTED

    # Biomechanical Movement Analysis Box (Right)
    add_card(19.8, 21.9, 15.0, 8.3, "04 — Biomechanical Movement Analysis")
    tx_bio = slide.shapes.add_textbox(Inches(20.2), Inches(22.9), Inches(14.2), Inches(7.0))
    tf_b = tx_bio.text_frame
    tf_b.word_wrap = True
    p = tf_b.paragraphs[0]
    p.text = "HOW AI UNDERSTANDS BODY MOVEMENT:"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = EMERALD

    p = tf_b.add_paragraph()
    p.text = "1. Keypoint Detection: Extracts 17 COCO landmarks (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles)."
    p.font.size = Pt(14)
    p.font.color.rgb = TEXT_DARK

    p = tf_b.add_paragraph()
    p.text = "2. Vector Joint Angle Formula:\n     θ = arccos( (BA · BC) / (|BA| × |BC|) )\n   Calculates angle at joint B using dot product between vectors BA and BC."
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = DARK_NAVY

    p = tf_b.add_paragraph()
    p.text = "3. State Machine Hysteresis:\n   Prevents false repetition counts near the threshold boundary.\n   • Sit-up Start: Torso angle > 140°\n   • Up Stage: Torso angle < 100°\n   • Count Rep: Return to > 140°"
    p.font.size = Pt(14)
    p.font.color.rgb = TEXT_DARK

    # ==========================================
    # 5. ROW 4: REAL SCREENSHOTS FROM THE WEBSITE
    # Y: 30.5 to 40.5 (Height: 9.8 inches)
    # ==========================================
    shots_card = add_card(1.2, 30.5, 33.6, 9.8, "05 — Production Application Interfaces & Assessment Results")

    # Image 1: Trainer Dashboard with Athletes
    img1_path = "access-control-evidence/01-trainer-a-dashboard.jpg"
    if os.path.exists(img1_path):
        slide.shapes.add_picture(img1_path, Inches(1.6), Inches(31.6), width=Inches(10.6), height=Inches(6.4))
        tx_c1 = slide.shapes.add_textbox(Inches(1.6), Inches(38.1), Inches(10.6), Inches(1.8))
        tf_c1 = tx_c1.text_frame
        tf_c1.word_wrap = True
        p = tf_c1.paragraphs[0]
        p.text = "FIGURE 1: TRAINER DASHBOARD"
        p.font.bold = True
        p.font.size = Pt(14)
        p.font.color.rgb = DARK_NAVY
        p2 = tf_c1.add_paragraph()
        p2.text = "Multi-athlete roster with live search, sport filtering, completed exercise count, and team assessment summaries."
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_MUTED

    # Image 2: Reports & Team Analytics
    img2_path = "access-control-evidence/09a-reports-trainer-a.jpg"
    if os.path.exists(img2_path):
        slide.shapes.add_picture(img2_path, Inches(12.7), Inches(31.6), width=Inches(10.6), height=Inches(6.4))
        tx_c2 = slide.shapes.add_textbox(Inches(12.7), Inches(38.1), Inches(10.6), Inches(1.8))
        tf_c2 = tx_c2.text_frame
        tf_c2.word_wrap = True
        p = tf_c2.paragraphs[0]
        p.text = "FIGURE 2: TEAM PERFORMANCE REPORTS"
        p.font.bold = True
        p.font.size = Pt(14)
        p.font.color.rgb = DARK_NAVY
        p2 = tf_c2.add_paragraph()
        p2.text = "Team average scores, top 5 athletes, exercise-wise score distribution bars, and weakest fitness module identification."
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_MUTED

    # Image 3: REAL CAMERA LIVE POSE ESTIMATION & EXERCISE ANALYSIS SCREENSHOT
    # Using Milestone 3_macro_image4.png (Actual webcam frame with YOLO 17-keypoint skeleton and angle analysis)
    img3_path = "poster_screenshots/Milestone 3_macro_image4.png"
    if not os.path.exists(img3_path):
        img3_path = "poster_screenshots/Milestone_4_macro_image10.png"
    if os.path.exists(img3_path):
        slide.shapes.add_picture(img3_path, Inches(23.8), Inches(31.6), width=Inches(10.6), height=Inches(6.4))
        tx_c3 = slide.shapes.add_textbox(Inches(23.8), Inches(38.1), Inches(10.6), Inches(1.8))
        tf_c3 = tx_c3.text_frame
        tf_c3.word_wrap = True
        p = tf_c3.paragraphs[0]
        p.text = "FIGURE 3: REAL-TIME POSE ESTIMATION & EXERCISE ANALYSIS"
        p.font.bold = True
        p.font.size = Pt(14)
        p.font.color.rgb = DARK_NAVY
        p2 = tf_c3.add_paragraph()
        p2.text = "Live webcam capture displaying YOLO26-Pose 17-keypoint skeleton extraction, joint-angle calculation, and real-time movement state analysis."
        p2.font.size = Pt(12)
        p2.font.color.rgb = TEXT_MUTED

    # ==========================================
    # 6. ROW 5: APPLICATIONS, FUTURE SCOPE, CONCLUSION
    # Y: 40.6 to 46.5 (Height: 5.9 inches)
    # ==========================================
    add_card(1.2, 40.6, 10.8, 5.8, "06 — Real-World Applications")
    tx_app = slide.shapes.add_textbox(Inches(1.5), Inches(41.6), Inches(10.2), Inches(4.5))
    tf_ap = tx_app.text_frame
    tf_ap.word_wrap = True
    apps = [
        "Sports Academies: Objective athletic grading and talent identification.",
        "Schools & Colleges: Standardized annual physical education fitness reports.",
        "Armed Forces / Police: Fatigue-free, automated physical eligibility tests.",
        "Physiotherapy Clinics: Rehabilitation recovery tracking & range of motion."
    ]
    for idx, a in enumerate(apps):
        p = tf_ap.paragraphs[0] if idx == 0 else tf_ap.add_paragraph()
        p.text = f"✔  {a}"
        p.font.size = Pt(14)
        p.font.color.rgb = TEXT_DARK

    add_card(12.6, 40.6, 10.8, 5.8, "07 — Future Scope")
    tx_fut = slide.shapes.add_textbox(Inches(12.9), Inches(41.6), Inches(10.2), Inches(4.5))
    tf_fu = tx_fut.text_frame
    tf_fu.word_wrap = True
    futs = [
        "Edge Device Acceleration: On-device mobile inference using WebAssembly/ONNX.",
        "Real-Time Voice Coaching: Live audio cues (e.g. 'Keep your back straight').",
        "Multi-Camera Triangulation: Dual-angle 3D skeletal tracking for rotational sports.",
        "National Database Integration: Export compliant with SAI / Khelo India standards."
    ]
    for idx, f in enumerate(futs):
        p = tf_fu.paragraphs[0] if idx == 0 else tf_fu.add_paragraph()
        p.text = f"✦  {f}"
        p.font.size = Pt(14)
        p.font.color.rgb = TEXT_DARK

    add_card(24.0, 40.6, 10.8, 5.8, "08 — Conclusion")
    tx_con = slide.shapes.add_textbox(Inches(24.3), Inches(41.6), Inches(10.2), Inches(4.5))
    tf_co = tx_con.text_frame
    tf_co.word_wrap = True
    p = tf_co.paragraphs[0]
    p.text = "The AI-Powered Fitness Assessment Platform bridges sports science and artificial intelligence."
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = DARK_NAVY
    
    p2 = tf_co.add_paragraph()
    p2.text = "By replacing manual counting with YOLO-based 17-keypoint pose estimation, joint-angle mathematics, and Celery asynchronous queuing, the platform eliminates human error and fatigue. The system delivers an objective, accessible, and production-ready solution for coaches and athletes."
    p2.font.size = Pt(14)
    p2.font.color.rgb = TEXT_DARK

    # ==========================================
    # 7. POSTER FOOTER (Height: 1.2 inches)
    # ==========================================
    footer_box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(46.8), Inches(36), Inches(1.2))
    footer_box.fill.solid()
    footer_box.fill.fore_color.rgb = DARK_NAVY
    footer_box.line.fill.background()
    
    gold_bottom = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(46.8), Inches(36), Inches(0.08))
    gold_bottom.fill.solid()
    gold_bottom.fill.fore_color.rgb = GOLD
    gold_bottom.line.fill.background()

    tf_foot = footer_box.text_frame
    p = tf_foot.paragraphs[0]
    p.text = "MADHAV INSTITUTE OF TECHNOLOGY & SCIENCE, GWALIOR · GWALIOR VIGYAN MAHOTSAV 2026 · ABV-IIITM GWALIOR"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER

    output_path = "c:\\Users\\91989\\OneDrive\\Desktop\\MACRO PROJECT\\AI_Fitness_Assessment_Poster_Updated.pptx"
    prs.save(output_path)
    try:
        prs.save("c:\\Users\\91989\\OneDrive\\Desktop\\MACRO PROJECT\\AI_Fitness_Assessment_Poster.pptx")
    except Exception:
        pass
    print(f"SUCCESS: Editable PowerPoint poster saved to {output_path}")

if __name__ == "__main__":
    build_poster()
