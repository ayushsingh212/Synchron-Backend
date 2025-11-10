import { Department } from "../models/department.model.js";

// ---------------------- Create Department ----------------------
export const createDepartment = async (req, res) => {
  try {
    const organisationId = req.organisation._id;
    const {  departmentName, description, headOfDepartment } = req.body;


    if (!organisationId || !departmentName) {
      return res.status(400).json({ message: "Organisation ID and Department Name are required" });
    }

    const newDepartment = new Department({
      organisationId,
      departmentName,
      description,
      headOfDepartment: headOfDepartment || null
    });

    await newDepartment.save();

    res.status(201).json({
      message: "Department created successfully",
      department: newDepartment,
    });
  } catch (error) {
    res.status(500).json({ message: "Error creating department", error: error.message });
  }
};

// ---------------------- Get All Departments (by Organisation) ----------------------
export const getDepartments = async (req, res) => {
  try {
    const  organisationId  = req.organisation._id;
    console.log("OrgId",organisationId);

    const departments = await Department.find({ organisationId })
      .populate("courses")
      .populate("facultyMembers")
      .populate("headOfDepartment");


    console.log("I have been hitted",departments)


    res.status(200).json(departments);
  } catch (error) {
    res.status(500).json({ message: "Error fetching departments", error: error.message });
  }
};

// ---------------------- Get Single Department ----------------------
export const getDepartmentById = async (req, res) => {
  try {
    const { id } = req.params;

    const department = await Department.findById(id)
      .populate("courses")
      .populate("facultyMembers")
      .populate("headOfDepartment");

    if (!department) return res.status(404).json({ message: "Department not found" });

    res.status(200).json(department);
  } catch (error) {
    res.status(500).json({ message: "Error fetching department", error: error.message });
  }
};

// ---------------------- Update Department ----------------------
export const updateDepartment = async (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;

    const updatedDepartment = await Department.findByIdAndUpdate(id, updates, { new: true })
      .populate("courses")
      .populate("facultyMembers")
      .populate("headOfDepartment");

    if (!updatedDepartment) return res.status(404).json({ message: "Department not found" });

    res.status(200).json({
      message: "Department updated successfully",
      department: updatedDepartment,
    });
  } catch (error) {
    res.status(500).json({ message: "Error updating department", error: error.message });
  }
};

// ---------------------- Delete Department ----------------------
export const deleteDepartment = async (req, res) => {
  try {
    console.log("I heejhabd")
    const { id } = req.params;
    console.log("here is the id",id)

    const deleted = await Department.findByIdAndDelete(id);
    if (!deleted) return res.status(404).json({ message: "Department not found" });

    res.status(200).json({ message: "Department deleted successfully" });
  } catch (error) {
    res.status(500).json({ message: "Error deleting department", error: error.message });
  }
};

// ---------------------- Add Course to Department ----------------------
export const addCourseToDepartment = async (req, res) => {
  try {
    const { departmentId, courseId } = req.body;

    const department = await Department.findById(departmentId);
    if (!department) return res.status(404).json({ message: "Department not found" });

    if (!department.courses.includes(courseId)) {
      department.courses.push(courseId);
      await department.save();
    }

    res.status(200).json({ message: "Course added to department", department });
  } catch (error) {
    res.status(500).json({ message: "Error adding course", error: error.message });
  }
};

// ---------------------- Add Faculty to Department ----------------------
export const addFacultyToDepartment = async (req, res) => {
  try {
    const { departmentId, facultyId } = req.body;

    const department = await Department.findById(departmentId);
    if (!department) return res.status(404).json({ message: "Department not found" });

    if (!department.facultyMembers.includes(facultyId)) {
      department.facultyMembers.push(facultyId);
      await department.save();
    }

    res.status(200).json({ message: "Faculty added to department", department });
  } catch (error) {
    res.status(500).json({ message: "Error adding faculty", error: error.message });
  }
};

// ---------------------- Assign / Change Head of Department ----------------------
export const assignHOD = async (req, res) => {
  try {
    const { departmentId, facultyId } = req.body;

    const department = await Department.findById(departmentId);
    if (!department) return res.status(404).json({ message: "Department not found" });

    department.headOfDepartment = facultyId;
    await department.save();

    const updated = await Department.findById(departmentId)
      .populate("courses")
      .populate("facultyMembers")
      .populate("headOfDepartment");

    res.status(200).json({
      message: "Head of Department assigned successfully",
      department: updated
    });
  } catch (error) {
    res.status(500).json({ message: "Error assigning HOD", error: error.message });
  }
};
