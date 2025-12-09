import asyncHandler from "../utils/asyncHandler.js";
import ApiResponse from "../utils/apiResponse.js";
import ApiError from "../utils/apiError.js";

import { FacultyTimetable } from "../models/facultyTimetable.model.js";
import { SectionTimetable } from "../models/sectionTimetable.model.js";


export const getOrganisationMasterTimetable = asyncHandler(async (req, res) => {
  const organisationId = req.organisation?._id || req.organisaton?.organisationId;
  
  if (!organisationId) {
    throw new ApiError(400, "organisationId is required");
  }

  // Use Promise.all for parallel fetching
  const [faculty, sections] = await Promise.all([
    FacultyTimetable.find({ organisationId })
      .select('course year semester faculty_id faculty_name department timetable periods')
      .lean(),
    SectionTimetable.find({ organisationId })
      .select('course year semester section_id section_name specialization timetable periods')
      .lean()
  ]);

  const master = {};

  // Process all entries
  [...faculty, ...sections].forEach(entry => {
    const { course, year, semester } = entry;
    
    // Create composite key
    const compositeKey = `${course}_${year}_${semester}`;
    
    if (!master[compositeKey]) {
      master[compositeKey] = {
        course,
        year,
        semester,
        faculty: [],
        sections: []
      };
    }
    
    // Determine if it's faculty or section
    if (entry.faculty_id) {
      // It's faculty
      master[compositeKey].faculty.push({
        faculty_id: entry.faculty_id,
        faculty_name: entry.faculty_name,
        department: entry.department,
        timetable: entry.timetable,
        periods: entry.periods
      });
    } else if (entry.section_id) {
      // It's section
      master[compositeKey].sections.push({
        section_id: entry.section_id,
        section_name: entry.section_name,
        specialization: entry.specialization,
        timetable: entry.timetable,
        periods: entry.periods
      });
    }
  });

  // Format response
  const response = {
    organisationId,
    courses: Object.keys(master).map(key => ({
      key,
      ...master[key],
      facultyCount: master[key].faculty.length,
      sectionsCount: master[key].sections.length,
      totalEntries: master[key].faculty.length + master[key].sections.length
    }))
  };

  return res.json(
    new ApiResponse(
      200,
      response,
      "Organisation master timetable retrieved successfully"
    )
  );
});
