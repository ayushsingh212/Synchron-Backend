import mongoose, { Schema } from 'mongoose';

const departmentSchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: 'Organisation',
      required: true
    },
    departmentName: {
      type: String,
      required: true,
      trim: true,
      lowercase: true
    },
    description: {
      type: String,
      trim: true
    },
    headOfDepartment: {
      type: Schema.Types.ObjectId,
      ref: 'Faculty',
      default: null
    },
    courses: [
      {
        type: Schema.Types.ObjectId,
        ref: 'Course'
      }
    ],
    facultyMembers: [
      {
        type: Schema.Types.ObjectId,
        ref: 'Faculty'
      }
    ]
  },
  { timestamps: true }
);

export const Department = mongoose.model('Department', departmentSchema);
