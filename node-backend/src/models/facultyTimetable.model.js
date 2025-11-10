// models/facultyTimetable.model.js
import mongoose, { Schema } from "mongoose";

const timetableSchema = new Schema(
  { 
    organisationId:{
      type:Schema.Types.ObjectId,
      ref:"Organisation"
    },
    faculty_id: { type: String, required: true},
    faculty_name: { type: String, required: true },
    department: { type: String, required: true },

    // store periods mapping (period number -> time slot)
    periods: { type: Map, of: String },

    // timetable: day -> period -> either "FREE" | "MENTORSHIP" | "LUNCH BREAK" | object (room, section, subject, type)
    timetable: {
      type: Map,
      of: {
        type: Map,
        of: Schema.Types.Mixed, // can hold strings or objects
      },
    },
  },
  { timestamps: true }
);

export const FacultyTimetable = mongoose.model("FacultyTimetable", timetableSchema);
