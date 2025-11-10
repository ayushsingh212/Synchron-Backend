import { Subject } from "../models/subject.model.js";

// ---------------------- Create Subject ----------------------
export const createSubject = async (req, res) => {
  try {
     
    console.log("I am the sub body",req.body)
     const organisationId = req.organisation._id;
    const { courseId, subjectName, subjectCode, hoursPerWeek, facultyOptions, fixedSlots } = req.body;

    if (!organisationId || !courseId || !subjectName || !subjectCode) {
      return res.status(400).json({ message: "Organisation, Course, Subject Name and Code are required" });
    }

    const newSubject = new Subject({
      organisationId,
      courseId,
      subjectName,
      subjectCode,
      hoursPerWeek: hoursPerWeek || 3,
      facultyOptions: facultyOptions || [],
      fixedSlots: fixedSlots || []
    });

    await newSubject.save();

    res.status(201).json({
      message: "Subject created successfully",
      subject: newSubject
    });
  } catch (error) {
    res.status(500).json({ message: "Error creating subject", error: error.message });
  }
};

// ---------------------- Get All Subjects by Organisation ----------------------
export const getSubjectsByOrganisation = async (req, res) => {
  try {
    const  organisationId  = req.organisation._id;

    const subjects = await Subject.find({ organisationId })
      .populate("courseId")
      .populate("facultyOptions");

    res.status(200).json(subjects);
  } catch (error) {
    res.status(500).json({ message: "Error fetching subjects", error: error.message });
  }
};

// ---------------------- Get Subjects by Course ----------------------
export const getSubjectsByCourse = async (req, res) => {
  try {
    const { courseId } = req.params;

    const subjects = await Subject.find({ courseId })
      .populate("facultyOptions");

    res.status(200).json(subjects);
  } catch (error) {
    res.status(500).json({ message: "Error fetching course subjects", error: error.message });
  }
};

// ---------------------- Get Single Subject ----------------------
export const getSubjectById = async (req, res) => {
  try {
    const { id } = req.params;

    const subject = await Subject.findById(id)
      .populate("courseId")
      .populate("facultyOptions");

    if (!subject) return res.status(404).json({ message: "Subject not found" });

    res.status(200).json(subject);
  } catch (error) {
    res.status(500).json({ message: "Error fetching subject", error: error.message });
  }
};

// ---------------------- Update Subject ----------------------
export const updateSubject = async (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;

    const updatedSubject = await Subject.findByIdAndUpdate(id, updates, { new: true })
      .populate("facultyOptions")
      .populate("courseId");

    if (!updatedSubject) return res.status(404).json({ message: "Subject not found" });

    res.status(200).json({
      message: "Subject updated successfully",
      subject: updatedSubject
    });
  } catch (error) {
    res.status(500).json({ message: "Error updating subject", error: error.message });
  }
};

// ---------------------- Delete Subject ----------------------
export const deleteSubject = async (req, res) => {
  try {
    const { id } = req.params;

    const deleted = await Subject.findByIdAndDelete(id);
    if (!deleted) return res.status(404).json({ message: "Subject not found" });

    res.status(200).json({ message: "Subject deleted successfully" });
  } catch (error) {
    res.status(500).json({ message: "Error deleting subject", error: error.message });
  }
};

// ---------------------- Assign Faculty Options ----------------------
export const assignFacultyToSubject = async (req, res) => {
  try {
    const { subjectId, facultyId } = req.body;

    const subject = await Subject.findById(subjectId);
    if (!subject) return res.status(404).json({ message: "Subject not found" });

    if (!subject.facultyOptions.includes(facultyId)) {
      subject.facultyOptions.push(facultyId);
      await subject.save();
    }

    res.status(200).json({ message: "Faculty added to subject options", subject });
  } catch (error) {
    res.status(500).json({ message: "Error assigning faculty", error: error.message });
  }
};

// ---------------------- Add Fixed Slot ----------------------
export const addFixedSlot = async (req, res) => {
  try {
    const { subjectId, day, slot } = req.body;

    const subject = await Subject.findById(subjectId);
    if (!subject) return res.status(404).json({ message: "Subject not found" });

    subject.fixedSlots.push({ day, slot });
    await subject.save();

    res.status(200).json({ message: "Fixed slot added successfully", subject });
  } catch (error) {
    res.status(500).json({ message: "Error adding fixed slot", error: error.message });
  }
};
