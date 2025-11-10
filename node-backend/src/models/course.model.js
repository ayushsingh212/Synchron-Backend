import mongoose, { Schema } from "mongoose";

const courseSchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: "Organisation",
      required: true,
    },
    departmentId: {
      type: Schema.Types.ObjectId,
      ref: "Department",
      required: true,
    },                       
     courseName: {
      type: String,
      required: true,
      trim: true,
      lowercase: true,
    },
    courseCode: {
      type: String,
      required: true,
      unique: true,
      uppercase: true,
      trim: true,
    },
    semester: {
      type: Number,
      required: true,
    },
    year: {
      type: Number, 
    },
    subjects: [
      {
        type: Schema.Types.ObjectId,
        ref: "Subject",
      },
    ],
    description: {
      type: String,
      trim: true,
    },
  },
  { timestamps: true }
);

export const Course = mongoose.model("Course", courseSchema);
