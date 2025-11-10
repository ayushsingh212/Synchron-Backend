import mongoose, { Schema } from 'mongoose';

const subjectSchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: 'Organisation',
      required: true
    },
    courseId: {
      type: Schema.Types.ObjectId,
      ref: 'Course',
      required: true
    },
    subjectName: {
      type: String,
      required: true,
      trim: true
    },
    subjectCode: {
      type: String,
      required: true,
      trim: true,
      uppercase: true
    },
    hoursPerWeek: {
      type: Number,
      default: 3
    },
    facultyOptions: [
      {
        type: Schema.Types.ObjectId,
        ref: 'Faculty'
      }
    ],
    fixedSlots: [
      {
        day: Number,
        slot: Number
      }
    ]
  },
  { timestamps: true }
);

export const Subject = mongoose.model('Subject', subjectSchema);
