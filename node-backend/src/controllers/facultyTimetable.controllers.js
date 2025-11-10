// controllers/pdf.controller.js
import PDFDocument from "pdfkit";
import axios from "axios";
import { FacultyTimetable } from "../models/facultyTimetable.model.js";

const FLASK_URL = process.env.FLASK_URL || "http://127.0.0.1:5000"; // adjust

// Generate + Save + Download All Faculty Timetables in one go
export const generateAndDownloadAllFacultyTimetables = async (req, res) => {
  try {
    console.log("Faculty timetable generation started...");

    // 1. Fetch from Flask
    const response = await axios.get(`${FLASK_URL}/api/timetables/faculty`);
    const apiResponse = response.data;

    if (!apiResponse || Object.keys(apiResponse).length === 0) {
      return res
        .status(404)
        .json({ success: false, message: "No faculty timetables received from API" });
    }

    console.log("Faculty timetables received from Flask");

    // 2. Save to MongoDB
    for (const faculty_id in apiResponse) {
      const facultyData = apiResponse[faculty_id];
      await FacultyTimetable.findOneAndUpdate(
        { faculty_id: facultyData.faculty_id },
        facultyData,
        { upsert: true, new: true }
      );
    }

    console.log("Faculty timetables saved to DB");

    // 3. Fetch back from DB to generate PDF
    const faculties = await FacultyTimetable.find();

    if (!faculties || faculties.length === 0) {
      return res
        .status(404)
        .json({ success: false, message: "No faculty timetables found in DB" });
    }

    // 4. Generate PDF
    const doc = new PDFDocument({ margin: 30, size: "A4" });

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader(
      "Content-Disposition",
      "attachment; filename=All_Faculty_Timetables.pdf"
    );

    doc.pipe(res);

    faculties.forEach((faculty, index) => {
      if (index > 0) doc.addPage();

      doc.fontSize(18).text(`Faculty Timetable: ${faculty.faculty_name}`, {
        align: "center",
      });
      doc.moveDown();
      doc.fontSize(12).text(`Department: ${faculty.department}`);
      doc.text(`Faculty ID: ${faculty.faculty_id}`);
      doc.moveDown();

      for (const [day, schedule] of faculty.timetable.entries()) {
        doc.fontSize(14).text(day, { underline: true });
        for (const [period, value] of schedule.entries()) {
          let text;
          if (typeof value === "string") {
            text = `${faculty.periods.get(period)} -> ${value}`;
          } else {
            text = `${faculty.periods.get(period)} -> ${value.subject} (${value.type}) | ${value.section} | Room: ${value.room}`;
          }
          doc.fontSize(12).text(text);
        }
        doc.moveDown();
      }
    });

    doc.end();
  } catch (err) {
    console.error("Error in generateAndDownloadAllFacultyTimetables:", err);
    res.status(500).json({
      success: false,
      message: "Error generating faculty timetable PDF",
    });
  }
};
