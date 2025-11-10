import { Router } from "express";
import { addCourseToDepartment, addFacultyToDepartment, assignHOD, createDepartment, deleteDepartment, getDepartmentById, getDepartments, updateDepartment } from "../controllers/department.controllers.js";
import { verifyJWT } from "../middlewares/auth.middleware.js";



const router = Router();

router.use(verifyJWT);



router.post("/createDepartment",createDepartment);
router.get("/getDepartments",getDepartments);
router.get("/getDepartmentById/:id",getDepartmentById);
router.put("/updateDepartment",updateDepartment);
router.delete("/deleteDepartment/:id",deleteDepartment)
router.put("/addCourseToDepartment",addCourseToDepartment);
router.put("/addFacultyToDepartment",addFacultyToDepartment);
router.post("/assignHOD",assignHOD);




export default router;