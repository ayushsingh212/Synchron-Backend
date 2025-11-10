import { Router } from "express";
import { verifyJWT } from "../middlewares/auth.middleware.js";
import { addFixedSlot, assignFacultyToSubject, createSubject, deleteSubject, getSubjectById, getSubjectsByCourse, getSubjectsByOrganisation, updateSubject } from "../controllers/subject.controllers.js";

const router = Router();


router.use(verifyJWT);

router.post("/createSubject",createSubject);
router.get("/getSubOrg",getSubjectsByOrganisation);
router.get("/getSubByCour",getSubjectsByCourse);
router.get("/getSub/:id",getSubjectById);
router.put("/update/:id",updateSubject);
router.delete("/delete/:id",deleteSubject);
router.put("/assignFac",assignFacultyToSubject);
router.put("addFixSlot",addFixedSlot);


export default router;