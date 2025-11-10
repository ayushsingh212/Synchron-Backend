function deepClone(obj){ return JSON.parse(JSON.stringify(obj)); }

/**
 * Input:
 *  { days, slotsPerDay, courses, rooms, subjects, faculties, maxAlternatives }
 * - courses: array of course objects with ._id and .subjects (subject ids)
 * - subjects: all subject docs (with hoursPerWeek, facultyOptions)
 * - faculties, rooms arrays
 *
 * Output: array of { courseId, grid } where grid is days x slotsPerDay with assignments:
 *  { subject: subjectId, faculty: facultyId, room: roomId } or null
 */
function generateTimetables({ days = 5, slotsPerDay = 6, courses = [], rooms = [], subjects = [], faculties = [], maxAlternatives = 2 }) {
  const results = [];

  // build subject lookup
  const subjMap = {};
  subjects.forEach(s => subjMap[String(s._id)] = s);

  // For each course, we independently try to build a grid satisfying hoursPerWeek for each subject.
  for (const course of courses) {
    const batchSubjects = (course.subjects || []).map(sid => subjMap[String(sid)]).filter(Boolean);
    if (batchSubjects.length === 0) continue;

    // build requirement list [{subjectId, remaining}]
    const reqs = batchSubjects.map(s => ({ subjectId: String(s._id), remaining: s.hoursPerWeek || 3 }));

    const gridEmpty = () => Array.from({ length: days }, () => Array.from({ length: slotsPerDay }, () => null));
    const maxCells = days * slotsPerDay;

    function facultyFree(facId, day, slot, assigned) {
      for (const a of assigned) {
        if (!a) continue;
        if (String(a.faculty) === String(facId) && a.day === day && a.slot === slot) return false;
      }
      return true;
    }

    function roomFree(roomId, day, slot, assigned) {
      for (const a of assigned) {
        if (!a) continue;
        if (String(a.room) === String(roomId) && a.day === day && a.slot === slot) return false;
      }
      return true;
    }

    const assigned = [];
    function backtrack(cellIndex, reqState) {
      if (results.length >= maxAlternatives) return true; // global limit
      if (cellIndex >= maxCells) {
        // check if all requirements satisfied
        const ok = reqState.every(r => r.remaining <= 0);
        if (ok) {
          // build grid
          const perGrid = gridEmpty();
          for (const a of assigned) {
            perGrid[a.day][a.slot] = { subject: a.subject, faculty: a.faculty, room: a.room };
          }
          results.push({ courseId: course._id, grid: perGrid });
        }
        return false;
      }
      const day = Math.floor(cellIndex / slotsPerDay);
      const slot = cellIndex % slotsPerDay;

      // try assign for any subject that has remaining > 0
      for (let i = 0; i < reqState.length; i++) {
        const cand = reqState[i];
        if (cand.remaining <= 0) continue;
        const subject = subjMap[cand.subjectId];
        if (!subject) continue;
        // iterate faculties who can teach this subject
        for (const facId of (subject.facultyOptions || [])) {
          // choose a room
          for (const room of rooms) {
            if (!facultyFree(facId, day, slot, assigned)) continue;
            if (!roomFree(room._id, day, slot, assigned)) continue;
            // assign
            cand.remaining -= 1;
            const asg = { course: course._id, subject: subject._id, faculty: facId, room: room._id, day, slot };
            assigned.push(asg);
            // next
            backtrack(cellIndex + 1, reqState);
            // backtrack
            assigned.pop();
            cand.remaining += 1;
            if (results.length >= maxAlternatives) return true;
          }
        }
      }

      // allow leaving empty
      return backtrack(cellIndex + 1, reqState);
    }

    const initialReq = deepClone(reqs);
    backtrack(0, initialReq);

    // If no result found for this course, push an empty grid to indicate failure
    if (results.filter(r => String(r.courseId) === String(course._id)).length === 0) {
      results.push({ courseId: course._id, grid: gridEmpty() });
    }
  }

  return results;
}

module.exports = { generateTimetables };
