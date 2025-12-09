import { Router } from "express";
import { verifyJWT } from "../middlewares/auth.middleware.js";
import { approveGeneratedSolution, checkGenerationStatus, generateByGivingData, getAFacultyTimetableID, getDetailedTimeTable, getFacultyTimeTables       , getFacultyTimetablesByGroup, getFacultyTimeTablesForSpecific, getGeneratedSolutionById, getGeneratedSolutions, getGeneratedSolutionsAll, getInfoPdf, getSectionTimetablesByGroup, getSectionTimeTablesDb, getSectionTimeTablesForSpecific, getSingleFacultyTimeTable, getSingleSectionTimeTable, startTimeTableCreation, updateFacultyTimetable } from "../controllers/timetable.controllers.js";
import {   generateAndDownloadAllFacultyTimetables } from "../controllers/facultyTimetable.controllers.js";
import {   updateSectionTimetable } from "../controllers/sectionTimetable.controllers.js";
import { upload } from "../middlewares/multer.middleware.js";
import { saveTimetable } from "../controllers/organisationData.controllers.js";
import { verifyAdminToken } from "../middlewares/admin.middleware.js";
import { verifySenateToken } from "../middlewares/senate.middleware.js";

const router = Router();


router.get("/facultyTime",getFacultyTimeTablesForSpecific)
router.get("/sectionTime",getSectionTimeTablesForSpecific)
router.use(verifyJWT)         

router.post("/generate",startTimeTableCreation);
router.get("/status",checkGenerationStatus);
router.get("/sections",getSectionTimeTablesDb)
router.get("/sections/:section_id",getSingleSectionTimeTable);
router.get("/faculty",getFacultyTimeTables);  
router.post("/upload-pdf",upload.single("file"),getInfoPdf);


 
router.get("/faculty/downloadAll",generateAndDownloadAllFacultyTimetables);   // in use
router.get("/faculty/:faculty_id",getAFacultyTimetableID);
router.get("/detailed",getDetailedTimeTable);







router.put("/sectionUpdate",updateSectionTimetable);
router.put("/facultyUpdate",updateFacultyTimetable);  
router.post("/saveData",saveTimetable)   // i th use


router.post("/sendData",generateByGivingData)


router.get("/sectionsTimeTables/group",getSectionTimetablesByGroup);
router.get("/faculty/group",getFacultyTimetablesByGroup);
router.get("/facultyTimeTable/getSpecific",getFacultyTimeTablesForSpecific);
router.get("/sectionTimeTable/getSpecific",getSectionTimeTablesForSpecific);


router.get("/solutions",verifySenateToken,getGeneratedSolutions);
router.get("/solutions/:id",verifySenateToken,getGeneratedSolutionById);
router.post("/solutions/approve",verifySenateToken,approveGeneratedSolution)



// 


router.use(verifyAdminToken)
router.get("/getAllGeneratedSolutions",getGeneratedSolutionsAll)


export default router;