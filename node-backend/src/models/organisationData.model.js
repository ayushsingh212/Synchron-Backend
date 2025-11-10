import mongoose, { Schema } from 'mongoose';

const organisationData = new mongoose.Schema({

  organisationId:{
    type:Schema.Types.ObjectId,
    ref:"Organisation"
  },
  college_info: {
    name: { type: String, required: true },
    session: { type: String, required: true },
    effective_date: { type: Date, required: true }
  },
  time_slots: {
    periods: [
      {
        id: Number,
        start_time: String,
        end_time: String
      }
    ],
    working_days: [String],
    break_periods: [Number],
    lunch_period: Number,
    mentorship_period: Number
  },
  departments: [
    {
      dept_id: String,
      name: String,
      sections: [
        {
          section_id: String,
          name: String,
          semester: String,
          year: String,
          room: String,
          student_count: Number,
          coordinator: String
        }
      ]
    }
  ],
  subjects: Array,
  labs: Array,
  faculty: Array,
  rooms: Array,
  constraints: {
    hard_constraints: Object,
    soft_constraints: Object
  },
  special_requirements: Object,
  genetic_algorithm_params: Object
}, { timestamps: true });

export const  OrganisationData =  mongoose.model('OrganisationData', organisationData);
