import mongoose, { Schema } from 'mongoose';

const facultySchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: 'Organisation',
      required: true
    },
    facultyName: {
      type: String,
      lowercase: true,
      trim: true,
      required: true
    },
    email: {
      type: String,
      unique: true,
      lowercase: true,
      required: true,
      trim: true
    },
    contactNumber: {
      type: String,
      unique: true
    },
    password: {
      type: String,
      required: true,
      trim: true
    },
    subjectsTaught: [
      {
        type: Schema.Types.ObjectId,
        ref: 'Subject'
      }
    ],
    coursesIn: [
      {
        type: Schema.Types.ObjectId,
        ref: 'Course'
      }
    ]
  },
  { timestamps: true }
);

export const Faculty = mongoose.model('Faculty', facultySchema);
