import { Course } from "../models/course.model.js";
import { Department } from "../models/department.model.js";
import { Subject } from "../models/subject.model.js";

/**
 * @desc Create a new Course
 * @route POST /api/courses
 * @access Private (Organisation Admin)
 */
export const createCourse = async (req, res) => {
  try {
    const organisationId  = req.organisation._id; // from auth
    const { departmentId, courseName, courseCode, semester, year, subjects, description } = req.body;

    // Validation
    if (!departmentId || !courseName || !courseCode || !semester) {
      return res.status(400).json({ message: "Required fields missing" });
    }

    // Ensure department exists
    const department = await Department.findById(departmentId);
    if (!department) return res.status(404).json({ message: "Department not found" });

    // Ensure unique courseCode
    const existingCourse = await Course.findOne({ courseCode });
    if (existingCourse) return res.status(409).json({ message: "Course code already exists" });

    // Optional: validate subjects exist
    if (subjects && subjects.length > 0) {
      const foundSubjects = await Subject.find({ _id: { $in: subjects } });
      if (foundSubjects.length !== subjects.length) {
        return res.status(400).json({ message: "One or more subjects invalid" });
      }
    }

    const course = await Course.create({
      organisationId,
      departmentId,
      courseName,
      courseCode,
      semester,
      year,
      subjects,
      description,
    });

    res.status(201).json({ message: "Course created successfully", course });
  } catch (err) {
    res.status(500).json({ message: "Error creating course", error: err.message });
  }
};

/**
 * @desc Update a Course
 * @route PUT /api/courses/:id
 * @access Private (Organisation Admin)
 */
export const updateCourse = async (req, res) => {
  try {
    const { id } = req.params;
    const { courseName, courseCode, semester, year, subjects, description } = req.body;

    let course = await Course.findById(id);
    if (!course) return res.status(404).json({ message: "Course not found" });

    if (courseCode && courseCode !== course.courseCode) {
      const existing = await Course.findOne({ courseCode });
      if (existing) return res.status(409).json({ message: "Course code already exists" });
    }

    course.courseName = courseName || course.courseName;
    course.courseCode = courseCode || course.courseCode;
    course.semester = semester || course.semester;
    course.year = year || course.year;
    course.subjects = subjects || course.subjects;
    course.description = description || course.description;

    await course.save();
    res.json({ message: "Course updated", course });
  } catch (err) {
    res.status(500).json({ message: "Error updating course", error: err.message });
  }
};

/**
 * @desc Delete a Course
 * @route DELETE /api/courses/:id
 * @access Private (Organisation Admin)
 */
export const deleteCourse = async (req, res) => {
  try {
    const { id } = req.params;
    const course = await Course.findByIdAndDelete(id);
    if (!course) return res.status(404).json({ message: "Course not found" });

    res.json({ message: "Course deleted successfully" });
  } catch (err) {
    res.status(500).json({ message: "Error deleting course", error: err.message });
  }
};

/**
 * @desc Get all Courses for an Organisation
 * @route GET /api/courses
 * @access Private (Organisation)
 */
export const getCourses = async (req, res) => {
  try {
    const  organisationId = req.organisation._id;
    const courses = await Course.find({ organisationId })
      .populate("departmentId", "departmentName")
      .populate("subjects", "subjectName subjectCode");

    res.json(courses);
  } catch (err) {
    res.status(500).json({ message: "Error fetching courses", error: err.message });
  }
};

/**
 * @desc Get single Course
 * @route GET /api/courses/:id
 * @access Private
 */
export const getCourseById = async (req, res) => {
  try {
    const { id } = req.params;
    const course = await Course.findById(id)
      .populate("departmentId", "departmentName")
      .populate("subjects", "subjectName subjectCode");

    if (!course) return res.status(404).json({ message: "Course not found" });

    res.json(course);
  } catch (err) {
    res.status(500).json({ message: "Error fetching course", error: err.message });
  }
};
