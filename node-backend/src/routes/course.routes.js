import { Router } from "express";
import { createCourse, deleteCourse, getCourseById, getCourses, updateCourse } from "../controllers/course.controllers.js";
import { verifyJWT } from "../middlewares/auth.middleware.js";


const router = Router();

router.use(verifyJWT)

router.post("/createCourse",createCourse);
router.put("/updateCourse",updateCourse);
router.delete("/delete/:id",deleteCourse);
router.get("/getCourses",getCourses);
router.get("/getCourse/:id",getCourseById);


export default router;