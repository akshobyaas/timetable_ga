// main.js
// Improved frontend to work with backend that returns slot_label/start/end.
// - renderTimetable now builds a day × time-range grid (uses slot_label/start).
// - serializeSlots includes start_time and end_time so backend can build labels.
// - robust sorting of time columns and fallbacks when start/end missing.

// ========== CONFIG ==========
const API_BASE = window.__ENV?.API_BASE || 'http://127.0.0.1:8000';

// ========== HELPERS ==========
const el = id => document.getElementById(id);
function showToast(msg, isError = false) {
  Toastify({
    text: msg,
    duration: 3000,
    close: true,
    gravity: "top",
    position: "right",
    stopOnFocus: true,
    style: {
      background: isError ? "#ef4444" : "#22c55e",
    },
  }).showToast();
}
function setStatus(msg, isError = false, showSpinner = false) {
  el('status').textContent = msg;
  el('status').style.color = isError ? '#ef4444' : 'inherit';

  if (showSpinner) {
    el('spinner').classList.remove('hidden');
  } else {
    el('spinner').classList.add('hidden');
  }

  // Only show toasts for important messages
  if (isError || msg.includes('generated') || msg.includes('downloaded') || msg.includes('loaded') || msg.includes('Sample')) {
    showToast(msg, isError);
  }
}
function createCell(html) { const td = document.createElement('td'); td.className = 'p-1'; td.innerHTML = html; return td; }
function fileFromString(text, filename) { const blob = new Blob([text], { type: 'text/csv' }); const file = new File([blob], filename, { type: 'text/csv' }); const dt = new DataTransfer(); dt.items.add(file); return dt.files; }

function handleFileInput(inputId, filenameId) {
  const input = el(inputId);
  const filenameEl = el(filenameId);
  if (!input || !filenameEl) return;
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (file) {
      filenameEl.textContent = file.name;
    } else {
      filenameEl.textContent = 'No file chosen';
    }
  });
}

// ========== SHOW / HIDE MANUAL AREA ==========
function showManualMode(enabled) {
  const manualArea = el('manualArea');
  const uploadForm = el('uploadForm');
  const subheading = el('subheading');
  if (enabled) {
    manualArea.classList.remove('hidden');
    uploadForm.classList.add('hidden');
    if (subheading) subheading.innerText = 'Enter data manually for courses, faculty, slots, and rooms. Click Generate.';
  } else {
    manualArea.classList.add('hidden');
    uploadForm.classList.remove('hidden');
    if (subheading) subheading.innerText = 'Upload 4 CSV files (courses, faculty, slots, rooms) or enter data manually. Click Generate.';
  }
}

// ---------- Row builders ----------
function addCourseRow(code = '', ltp = '', faculty_id = '', student_group = '', student_count = '', lec_room_type = 'LectureHall', lab_room_type = 'ComputerLab') {
  const tbody = el('coursesTable').querySelector('tbody');
  const tr = document.createElement('tr');
  tr.className = 'bg-white border-b';
  tr.appendChild(createCell(`<input aria-label="Course code" placeholder="CS101" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${code}">`));
  tr.appendChild(createCell(`<input aria-label="L-T-P" placeholder="3-0-2" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${ltp}">`));
  tr.appendChild(createCell(`<input aria-label="Faculty ID" placeholder="F1" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${faculty_id}">`));
  tr.appendChild(createCell(`<input aria-label="Student Group" placeholder="CS_Year2" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${student_group}">`));
  tr.appendChild(createCell(`<input aria-label="Student Count" placeholder="60" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" type="number" min="1" value="${student_count || 1}">`));
  tr.appendChild(createCell(`<input aria-label="Lecture Room Type" placeholder="LectureHall" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${lec_room_type}">`));
  tr.appendChild(createCell(`<input aria-label="Lab Room Type" placeholder="ComputerLab" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${lab_room_type}">`));
  tr.appendChild(createCell(`<button type="button" class="remove-row text-sm px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded">Remove</button>`));
  tbody.appendChild(tr);

  tr.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', realtimeValidate);
  });
  realtimeValidate();
}

function addFacultyRow(id = '', name = '') {
  const tbody = el('facultyTable').querySelector('tbody');
  const tr = document.createElement('tr');
  tr.className = 'bg-white border-b';
  tr.appendChild(createCell(`<input aria-label="Faculty ID" placeholder="F1" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${id}">`));
  tr.appendChild(createCell(`<input aria-label="Faculty Name" placeholder="Prof. Smith" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${name}">`));
  tr.appendChild(createCell(`<button type="button" class="remove-row text-sm px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded">Remove</button>`));
  tbody.appendChild(tr);

  tr.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', realtimeValidate);
  });
  realtimeValidate();
}

function addRoomRow(id = '', type = 'LectureHall', capacity = '') {
  const tbody = el('roomsTable').querySelector('tbody');
  const tr = document.createElement('tr');
  tr.className = 'bg-white border-b';
  tr.appendChild(createCell(`<input aria-label="Room ID" placeholder="CR101" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${id}">`));
  tr.appendChild(createCell(`<input aria-label="Room Type" placeholder="LectureHall" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" value="${type}">`));
  tr.appendChild(createCell(`<input aria-label="Capacity" placeholder="60" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md" type="number" min="1" value="${capacity || 1}">`));
  tr.appendChild(createCell(`<button type="button" class="remove-row text-sm px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded">Remove</button>`));
  tbody.appendChild(tr);

  tr.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', realtimeValidate);
  });
  realtimeValidate();
}

function addSlotRow(id = '', day = '', start_time = '', end_time = '', type = 'Class') {
  const tbody = el('slotsTable').querySelector('tbody');
  const tr = document.createElement('tr');
  tr.className = 'bg-white';

  tr.appendChild(createCell(`<input aria-label="Day" placeholder="Mon" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md slot-day" value="${day}">`));
  tr.appendChild(createCell(`<input aria-label="Start time" type="time" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md slot-start" value="${start_time}">`));
  tr.appendChild(createCell(`<input aria-label="End time" type="time" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 rounded-md slot-end" value="${end_time}">`));
  tr.appendChild(createCell(`<select aria-label="Slot type" class="w-full text-sm p-1 bg-white border border-gray-300 rounded-md slot-type">
    <option ${type === 'Class' ? 'selected' : ''}>Class</option>
    <option ${type === 'Break' ? 'selected' : ''}>Break</option>
    <option ${type === 'Lunch' ? 'selected' : ''}>Lunch</option>
    <option ${type === 'Holiday' ? 'selected' : ''}>Holiday</option>
  </select>`));

  const actionHtml = `
    <div class="flex gap-2 justify-end">
      <button type="button" class="remove-row text-sm px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded">Remove</button>
      <button type="button" class="mark-day-btn text-sm px-2 py-1 bg-yellow-400 text-black rounded">Mark day Holiday</button>
    </div>
  `;
  tr.appendChild(createCell(actionHtml));
  tbody.appendChild(tr);

  tr.querySelectorAll('input, select').forEach(input => {
    input.addEventListener('input', realtimeValidate);
  });
  tr.querySelectorAll('.slot-day, .slot-type').forEach(inp => inp.addEventListener('input', () => updateAllMarkButtons()));
  updateAllMarkButtons();
  realtimeValidate();
}

// ---------- Delegated click handling ----------
document.addEventListener('click', (ev) => {
  if (ev.target && ev.target.classList.contains('remove-row')) {
    const tr = ev.target.closest('tr');
    if (tr) {
      tr.remove();
      updateAllMarkButtons();
      realtimeValidate();
    }
    return;
  }

  if (ev.target && ev.target.classList.contains('mark-day-btn')) {
    const tr = ev.target.closest('tr');
    if (!tr) return;
    const dayInput = tr.querySelector('.slot-day');
    if (!dayInput) return;
    const day = (dayInput.value || '').trim();
    if (!day) { setStatus('Set the Day field (e.g. Mon) for this row first', true, false); return; }

    const tbody = el('slotsTable').querySelector('tbody');
    const allRows = Array.from(tbody.querySelectorAll('tr'));
    const rowsForDay = allRows.filter(r => ((r.querySelector('.slot-day')?.value || '').trim().toLowerCase()) === day.toLowerCase());
    const onlyHoliday = rowsForDay.length > 0 && rowsForDay.every(r => (r.querySelector('.slot-type')?.value || '') === 'Holiday');

    if (onlyHoliday) {
      removeHolidayForDay(day);
      setStatus(`${day} unmarked as holiday`, false, false);
    } else {
      if (rowsForDay.length > 0) {
        const proceed = confirm(`This will remove ${rowsForDay.length} existing slot row(s) for ${day} and mark the whole day as Holiday. Continue?`);
        if (!proceed) return;
      }
      addHolidayForDay(day);
      setStatus(`${day} marked as holiday`, false, false);
    }
    updateAllMarkButtons();
    return;
  }
});

// ---------- Holiday helpers ----------
function addHolidayForDay(day) {
  const tbody = el('slotsTable').querySelector('tbody');
  Array.from(tbody.querySelectorAll('tr')).forEach(r => {
    const d = (r.querySelector('.slot-day')?.value || '').trim();
    if (d.toLowerCase() === day.toLowerCase()) r.remove();
  });
  addSlotRow('', day, '', '', 'Holiday');
  updateAllMarkButtons();
}

function removeHolidayForDay(day) {
  const tbody = el('slotsTable').querySelector('tbody');
  Array.from(tbody.querySelectorAll('tr')).forEach(r => {
    const d = (r.querySelector('.slot-day')?.value || '').trim();
    const t = (r.querySelector('.slot-type')?.value || '').trim();
    if (d.toLowerCase() === day.toLowerCase() && t === 'Holiday') r.remove();
  });
  updateAllMarkButtons();
}

function updateAllMarkButtons() {
  const tbody = el('slotsTable').querySelector('tbody');
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const dayMap = {};
  rows.forEach(r => {
    const d = (r.querySelector('.slot-day')?.value || '').trim();
    const t = (r.querySelector('.slot-type')?.value || '').trim();
    if (!d) return;
    const k = d.toLowerCase();
    if (!dayMap[k]) dayMap[k] = { count: 0, holidayCount: 0 };
    dayMap[k].count++;
    if (t === 'Holiday') dayMap[k].holidayCount++;
  });

  rows.forEach(r => {
    const btn = r.querySelector('.mark-day-btn');
    const dayVal = (r.querySelector('.slot-day')?.value || '').trim();
    if (!btn) return;
    if (!dayVal) {
      btn.disabled = true;
      btn.innerText = 'Mark day Holiday';
      btn.classList.remove('bg-green-400'); btn.classList.add('bg-yellow-400');
      return;
    }
    btn.disabled = false;
    const info = dayMap[dayVal.toLowerCase()] || null;
    if (info && info.count > 0 && info.holidayCount === info.count) {
      btn.innerText = 'Unmark day';
      btn.classList.remove('bg-yellow-400'); btn.classList.add('bg-green-400');
    } else {
      btn.innerText = 'Mark day Holiday';
      btn.classList.remove('bg-green-400'); btn.classList.add('bg-yellow-400');
    }
  });
}

function realtimeValidate() {
  const courseCodes = new Set();
  const facultyIds = new Set();
  const roomIds = new Set();
  const roomTypes = new Set();

  // Validate Faculty
  const allFacultyRows = Array.from(el('facultyTable').querySelectorAll('tbody tr'));
  allFacultyRows.forEach((r, i) => {
    const inputs = r.querySelectorAll('input');
    const idInput = inputs[0];
    const nameInput = inputs[1];

    const id = idInput.value.trim();
    const name = nameInput.value.trim();

    const isDuplicate = allFacultyRows.some((otherRow, otherIdx) => otherIdx !== i && otherRow.querySelector('input').value.trim() === id);
    idInput.classList.toggle('input-error', !id || isDuplicate);
    nameInput.classList.toggle('input-error', !name);
    if (id) facultyIds.add(id);
  });

  // Validate Rooms
  const allRoomRows = Array.from(el('roomsTable').querySelectorAll('tbody tr'));
  allRoomRows.forEach((r, i) => {
    const inputs = r.querySelectorAll('input');
    const idInput = inputs[0];
    const typeInput = inputs[1];
    const capacityInput = inputs[2];

    const id = idInput.value.trim();
    const type = typeInput.value.trim();
    const capacity = capacityInput.value.trim();

    const isDuplicate = allRoomRows.some((otherRow, otherIdx) => otherIdx !== i && otherRow.querySelector('input').value.trim() === id);
    idInput.classList.toggle('input-error', !id || isDuplicate);
    typeInput.classList.toggle('input-error', !type);
    capacityInput.classList.toggle('input-error', !capacity || parseInt(capacity) < 1);
    if (id) roomIds.add(id);
    if (type) roomTypes.add(type);
  });

  // Validate Courses
  const allCourseRows = Array.from(el('coursesTable').querySelectorAll('tbody tr'));
  allCourseRows.forEach((r, i) => {
    const inputs = r.querySelectorAll('input');
    const codeInput = inputs[0];
    const ltpInput = inputs[1];
    const facultyIdInput = inputs[2];
    const studentGroupInput = inputs[3];
    const studentCountInput = inputs[4];
    const lecRoomTypeInput = inputs[5];
    const labRoomTypeInput = inputs[6];

    const code = codeInput.value.trim();
    const ltp = ltpInput.value.trim();
    const facultyId = facultyIdInput.value.trim();
    const studentGroup = studentGroupInput.value.trim();
    const studentCount = studentCountInput.value.trim();
    const lecRoomType = lecRoomTypeInput.value.trim();
    const labRoomType = labRoomTypeInput.value.trim();

    // Course Code validation
    const isDuplicateCode = allCourseRows.some((otherRow, otherIdx) => otherIdx !== i && otherRow.querySelector('input').value.trim() === code);
    codeInput.classList.toggle('input-error', !code || isDuplicateCode);
    if (code) courseCodes.add(code);

    // L-T-P validation (simple format check)
    const ltpRegex = /^\d+-\d+-\d+$/;
    ltpInput.classList.toggle('input-error', !ltp || !ltpRegex.test(ltp));

    // Faculty ID validation
    facultyIdInput.classList.toggle('input-error', !facultyId || !facultyIds.has(facultyId));

    // Student Group validation (ensure one group for now)
    studentGroupInput.classList.toggle('input-error', !studentGroup);
    // TODO: Add logic to ensure only one unique student group is entered across all courses

    // Student Count validation
    studentCountInput.classList.toggle('input-error', !studentCount || parseInt(studentCount) < 1);

    // Room Type validation
    lecRoomTypeInput.classList.toggle('input-error', !lecRoomType || !roomTypes.has(lecRoomType));
    labRoomTypeInput.classList.toggle('input-error', !labRoomType || !roomTypes.has(labRoomType));
  });

  const slotRows = Array.from(el('slotsTable').querySelectorAll('tbody tr'));
  slotRows.forEach((r) => {
    const inputs = r.querySelectorAll('input, select');
    const dayInput = inputs[0];
    const startInput = inputs[1];
    const endInput = inputs[2];
    const type = (inputs[3]?.value || 'Class').trim();

    if (type === 'Class') {
      dayInput.classList.toggle('input-error', !dayInput.value.trim());
      startInput.classList.toggle('input-error', !startInput.value.trim());
      endInput.classList.toggle('input-error', !endInput.value.trim());
      const start = startInput.value.trim();
      const end = endInput.value.trim();
      if (start && end && start >= end) {
        startInput.classList.add('input-error');
        endInput.classList.add('input-error');
      } else if (!start) {
        startInput.classList.add('input-error');
      } else if (!end) {
        endInput.classList.add('input-error');
      }
    } else {
      dayInput.classList.remove('input-error');
      startInput.classList.remove('input-error');
      endInput.classList.remove('input-error');
    }
  });
}

function validateManualData() {
  realtimeValidate();
  const hasErrors = document.querySelector('#manualArea .input-error');
  if (hasErrors) {
    setStatus('Please fix the errors highlighted in red.', true, false);
    return false;
  }
  return true;
}

// ---------- Utility: parse HH:MM to minutes (for sorting) ----------
function timeToMinutes(t) {
  if (!t || typeof t !== 'string') return null;
  const m = t.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  const hh = parseInt(m[1], 10);
  const mm = parseInt(m[2], 10);
  return hh * 60 + mm;
}

// ========== MAIN DOM READY / EVENT WIRING ========== 
document.addEventListener('DOMContentLoaded', () => {
  // File input handlers
  handleFileInput('courses', 'courses-filename');
  handleFileInput('faculty', 'faculty-filename');
  handleFileInput('slots', 'slots-filename');
  handleFileInput('rooms', 'rooms-filename'); // New rooms file input

  // add-row handlers
  el('addCourse').addEventListener('click', () => addCourseRow());
  el('addFaculty').addEventListener('click', () => addFacultyRow());
  el('addRoom').addEventListener('click', () => addRoomRow()); // New room row
  el('addSlot').addEventListener('click', () => addSlotRow());

  // open modal builder
  el('addCommonDay').addEventListener('click', openCommonDayBuilder);

  // initial rows
  if (el('coursesTable').querySelector('tbody').children.length === 0) addCourseRow();
  if (el('facultyTable').querySelector('tbody').children.length === 0) addFacultyRow();
  if (el('roomsTable').querySelector('tbody').children.length === 0) addRoomRow(); // Initial room row
  if (el('slotsTable').querySelector('tbody').children.length === 0) addSlotRow();

  // mode radios - use change so keyboard toggles work
  const modeUploadEl = el('modeUpload'), modeManualEl = el('modeManual');
  if (modeUploadEl && modeManualEl) {
    modeUploadEl.addEventListener('change', () => showManualMode(false));
    modeManualEl.addEventListener('change', () => showManualMode(true));
    // set initial UI according to checked radio
    showManualMode(modeManualEl.checked);
  }

  // sample button
  el('sampleBtn').addEventListener('click', () => {
    try {
      // New sample data for L-T-P courses, faculty, rooms, and slots
      const coursesCsv = "course_code,ltp,faculty_id,student_group,student_count,required_room_type_lecture,required_room_type_lab\nCS201,3-0-2,F1,CS_Year2,60,LectureHall,ComputerLab\nMA201,3-1-0,F2,CS_Year2,60,LectureHall,None\nPH201,2-0-2,F3,CS_Year2,60,LectureHall,PhysicsLab\n";
      const facultyCsv = "id,name\nF1,Prof. Alice\nF2,Prof. Bob\nF3,Dr. Carol\n";
      const roomsCsv = "room_id,room_type,capacity\nLH101,LectureHall,70\nCL101,ComputerLab,30\nPL101,PhysicsLab,30\n";
      const slotsCsv = "day,slot_index,start_time,end_time,type\nMon,0,09:00,10:00,Class\nMon,1,10:00,11:00,Class\nMon,2,11:00,12:00,Class\nMon,3,12:00,13:00,Break\nMon,4,13:00,14:00,Class\nMon,5,14:00,15:00,Class\nTue,0,09:00,10:00,Class\nTue,1,10:00,11:00,Class\nTue,2,11:00,12:00,Class\nTue,3,12:00,13:00,Break\nTue,4,13:00,14:00,Class\nTue,5,14:00,15:00,Class\n";

      if (el('modeManual').checked) {
        el('coursesTable').querySelector('tbody').innerHTML = '';
        el('facultyTable').querySelector('tbody').innerHTML = '';
        el('roomsTable').querySelector('tbody').innerHTML = '';
        el('slotsTable').querySelector('tbody').innerHTML = '';

        coursesCsv.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addCourseRow(parts[0]?.trim(), parts[1]?.trim(), parts[2]?.trim(), parts[3]?.trim(), parts[4]?.trim(), parts[5]?.trim(), parts[6]?.trim());
        });

        facultyCsv.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addFacultyRow(parts[0]?.trim(), parts[1]?.trim());
        });

        roomsCsv.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addRoomRow(parts[0]?.trim(), parts[1]?.trim(), parts[2]?.trim());
        });

        slotsCsv.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addSlotRow('', parts[0]?.trim(), parts[2]?.trim(), parts[3]?.trim(), parts[4]?.trim());
        });

        setStatus('Sample manual data loaded. Edit if needed and click Generate.');
        setTimeout(updateAllMarkButtons, 50);
        return;
      }

      // upload mode sample
      const coursesInput = el('courses');
      const facultyInput = el('faculty');
      const slotsInput = el('slots');
      const roomsInput = el('rooms');

      coursesInput.files = fileFromString(coursesCsv, 'courses.csv');
      facultyInput.files = fileFromString(facultyCsv, 'faculty.csv');
      slotsInput.files = fileFromString(slotsCsv, 'slots.csv');
      roomsInput.files = fileFromString(roomsCsv, 'rooms.csv');

      // Manually trigger change event to update filename display
      coursesInput.dispatchEvent(new Event('change'));
      facultyInput.dispatchEvent(new Event('change'));
      slotsInput.dispatchEvent(new Event('change'));
      roomsInput.dispatchEvent(new Event('change'));

      setStatus('Sample data loaded in inputs. Click Generate.');
    } catch (err) {
      console.error('Sample button error', err);
      setStatus('Error preparing sample data: ' + (err && err.message), true, false);
    }
  });

  // generate button wiring
  const generateBtn = el('generateBtn');
  if (generateBtn) {
    generateBtn.addEventListener('click', async () => {
      try {
        setStatus('Validating input...', false, false);
        const manualMode = el('modeManual').checked;

        if (manualMode) {
          if (!validateManualData()) {
            generateBtn.disabled = false;
            return;
          }
        }

        function stringToFile(content, filename = 'file.csv') {
          const blob = new Blob([content], { type: 'text/csv' });
          try { return new File([blob], filename, { type: 'text/csv' }); } 
          catch (e) { const dt = new DataTransfer(); dt.items.add(new File([blob], filename, { type: 'text/csv' })); return dt.files[0]; } 
        }

        function serializeCourses() {
          const rows = Array.from(el('coursesTable').querySelectorAll('tbody tr'));
          if (rows.length === 0) return null;
          const lines = ["course_code,ltp,faculty_id,student_group,student_count,required_room_type_lecture,required_room_type_lab"];
          for (const r of rows) {
            const inputs = r.querySelectorAll('input');
            const code = (inputs[0]?.value || '').trim();
            const ltp = (inputs[1]?.value || '').trim();
            const facultyId = (inputs[2]?.value || '').trim();
            const studentGroup = (inputs[3]?.value || '').trim();
            const studentCount = (inputs[4]?.value || '1').trim();
            const lecRoomType = (inputs[5]?.value || '').trim();
            const labRoomType = (inputs[6]?.value || '').trim();
            if (!code) continue;
            lines.push(`${code},${ltp},${facultyId},${studentGroup},${studentCount},${lecRoomType},${labRoomType}`);
          }
          return lines.join('\n');
        }

        function serializeFaculty() {
          const rows = Array.from(el('facultyTable').querySelectorAll('tbody tr'));
          if (rows.length === 0) return null;
          const lines = ["id,name"];
          for (const r of rows) {
            const inputs = r.querySelectorAll('input');
            const id = (inputs[0]?.value || '').trim();
            const name = (inputs[1]?.value || '').trim();
            if (!id) continue;
            lines.push(`${id},${name}`);
          }
          return lines.join('\n');
        }

        function serializeRooms() {
          const rows = Array.from(el('roomsTable').querySelectorAll('tbody tr'));
          if (rows.length === 0) return null;
          const lines = ["room_id,room_type,capacity"];
          for (const r of rows) {
            const inputs = r.querySelectorAll('input');
            const id = (inputs[0]?.value || '').trim();
            const type = (inputs[1]?.value || '').trim();
            const capacity = (inputs[2]?.value || '1').trim();
            if (!id) continue;
            lines.push(`${id},${type},${capacity}`);
          }
          return lines.join('\n');
        }

        // NOTE: include start_time and end_time in serialized slots so backend can build slot_label
        function serializeSlots() {
          const rows = Array.from(el('slotsTable').querySelectorAll('tbody tr'));
          if (rows.length === 0) return null;
          const lines = ['day,slot_index,start_time,end_time,type'];
          // group by day to produce slot_index sequence per day
          const dayGroups = {};
          for (const r of rows) {
            const inputs = r.querySelectorAll('input, select');
            const day = (inputs[0]?.value || '').trim();
            const start = (inputs[1]?.value || '').trim();
            const end = (inputs[2]?.value || '').trim();
            const type = (inputs[3]?.value || 'Class').trim();
            if (!day) continue;
            if (!(day in dayGroups)) dayGroups[day] = [];
            dayGroups[day].push({ start, end, type });
          }
          for (const day of Object.keys(dayGroups)) {
            // sort day slots by start time if possible so indices are stable
            const blocks = dayGroups[day];
            blocks.sort((a, b) => {
              const ta = timeToMinutes(a.start) ?? 0;
              const tb = timeToMinutes(b.start) ?? 0;
              return ta - tb;
            });
            let idx = 0;
            for (const block of blocks) {
              // only include Class slots as assignable (consistent with backend)
              const slotId = `${day.toLowerCase()}-${idx}`;
              lines.push(`${slotId},${day},${idx},${block.start || ''},${block.end || ''},${block.type || 'Class'}`);
              idx++;
            }
          }
          return lines.join('\n');
        }

        setStatus('Preparing data...', false, true);
        generateBtn.disabled = true;

        const fd = new FormData();

        if (manualMode) {
          const coursesCsv = serializeCourses();
          const facultyCsv = serializeFaculty();
          const slotsCsv = serializeSlots();
          const roomsCsv = serializeRooms();

          if (!coursesCsv || !facultyCsv || !slotsCsv || !roomsCsv) {
            setStatus('Please fill all courses, faculty, slots, and rooms tables before generating.', true, false);
            generateBtn.disabled = false;
            return;
          }

          fd.append('courses', stringToFile(coursesCsv, 'courses.csv'));
          fd.append('faculty', stringToFile(facultyCsv, 'faculty.csv'));
          fd.append('slots', stringToFile(slotsCsv, 'slots.csv'));
          fd.append('rooms', stringToFile(roomsCsv, 'rooms.csv'));
        } else {
          const courses = el('courses').files[0];
          const faculty = el('faculty').files[0];
          const slots = el('slots').files[0];
          const rooms = el('rooms').files[0];

          if (!courses || !faculty || !slots || !rooms) {
            setStatus('Please attach all four CSV files (courses, faculty, slots, rooms) or switch to manual entry.', true, false);
            generateBtn.disabled = false;
            return;
          }

          fd.append('courses', courses);
          fd.append('faculty', faculty);
          fd.append('slots', slots);
          fd.append('rooms', rooms);
        }

        setStatus('Uploading & generating timetable — please wait...', false, true);

        const res = await fetch(API_BASE + '/generate', { method: 'POST', body: fd });
        if (!res.ok) {
          const errText = await res.text().catch(() => null);
          let err = null;
          try { err = JSON.parse(errText); } catch (e) { err = null; } 
          setStatus('Server error: ' + (err?.detail || err?.error || res.status), true, false);
          generateBtn.disabled = false;
          return;
        }

        const data = await res.json();
        setStatus('Timetable generated.', false, false);
        renderTimetable(data.assignments || []);
        generateBtn.disabled = false;
      } catch (err) {
        console.error('Generate handler error', err);
        setStatus('Error during generation: ' + (err && err.message), true, false);
        try { generateBtn.disabled = false; } catch (e) { } 
      }
    });
  }

  el('downloadImage').addEventListener('click', () => {
    const filename = 'timetable_' + new Date().toISOString().replace(/[:.]/g, '-') + '.png';
    downloadTimetableImage(filename);
  });

  updateAllMarkButtons();
});

// ========== COMMON DAY BUILDER (modal) ========== 
function openCommonDayBuilder() {
  const modalRoot = el('modalRoot'); modalRoot.innerHTML = '';
  const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop';
  const modal = document.createElement('div'); modal.className = 'modal';

  modal.innerHTML = `
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-lg font-semibold">Create common slots for a day</h3>
      <div><button id="closeCommonDay" class="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 btn-small">Close</button></div>
    </div>
    <div class="space-y-3">
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-sm">Template Day (source)</label>
          <select id="templateDaySelect" class="w-full p-2 border rounded bg-white border-gray-300">
            <option>Mon</option><option>Tue</option><option>Wed</option><option>Thu</option><option>Fri</option><option>Sat</option><option>Sun</option>
          </select>
        </div>
        <div>
          <label class="text-sm">Copy to (target days)</label>
          <div class="mt-1 grid grid-cols-4 gap-2">
            <label class="chip"><input type="checkbox" value="Mon">Mon</label>
            <label class="chip"><input type="checkbox" value="Tue">Tue</label>
            <label class="chip"><input type="checkbox" value="Wed">Wed</label>
            <label class="chip"><input type="checkbox" value="Thu">Thu</label>
            <label class="chip"><input type="checkbox" value="Fri">Fri</label>
            <label class="chip"><input type="checkbox" value="Sat">Sat</label>
            <label class="chip"><input type="checkbox" value="Sun">Sun</label>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <label class="inline-flex items-center gap-2"><input id="markHoliday" type="checkbox"> Mark template day as <strong>Holiday</strong></label>
        <label class="inline-flex items-center gap-2"><input id="targetHoliday" type="checkbox"> When copying, mark targets as Holiday too</label>
      </div>

      <div>
        <label class="text-sm font-medium">Template slots (use + to add)</label>
        <div id="templateSlots" class="space-y-2 mt-2"></div>
        <div class="mt-2">
          <button id="tplAddSlot" class="px-3 py-1 bg-indigo-600 text-white rounded btn-small">+ Add template slot</button>
          <button id="tplClear" class="ml-2 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded btn-small">Clear template</button>
        </div>
        <div class="text-xs text-gray-500 mt-2">Use time pickers for start/end. Template entries define slots that will be applied to the selected target days.</div>
      </div>

      <div class="mt-4 flex justify-end gap-2">
        <button id="tplApply" class="px-4 py-2 bg-indigo-600 text-white rounded">Apply to selected days</button>
        <button id="tplCancel" class="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded">Cancel</button>
      </div>
    </div>
  `;

  backdrop.appendChild(modal); modalRoot.appendChild(backdrop);

  const tplSlotsDiv = modal.querySelector('#templateSlots');
  function createTemplateSlotRow(start = '09:00', end = '10:00', type = 'Class') {
    const div = document.createElement('div'); div.className = 'flex gap-2 items-center';
    div.innerHTML = `
      <input type="time" class="tpl-start p-1 border rounded bg-white border-gray-300" value="${start}">
      <input type="time" class="tpl-end p-1 border rounded bg-white border-gray-300" value="${end}">
      <select class="tpl-type p-1 border rounded bg-white border-gray-300">
        <option ${type === 'Class' ? 'selected' : ''}>Class</option>
        <option ${type === 'Break' ? 'selected' : ''}>Break</option>
        <option ${type === 'Lunch' ? 'selected' : ''}>Lunch</option>
        <option ${type === 'Holiday' ? 'selected' : ''}>Holiday</option>
      </select>
      <button class="tpl-remove px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded btn-small">Remove</button>
    `;
    tplSlotsDiv.appendChild(div);
    div.querySelector('.tpl-remove').addEventListener('click', ()=> { div.remove(); });
  }

  createTemplateSlotRow();
  modal.querySelector('#closeCommonDay').addEventListener('click', () => { modalRoot.innerHTML = ''; });
  modal.querySelector('#tplAddSlot').addEventListener('click', () => createTemplateSlotRow());
  modal.querySelector('#tplClear').addEventListener('click', () => { tplSlotsDiv.innerHTML = ''; });
  modal.querySelector('#tplCancel').addEventListener('click', () => { modalRoot.innerHTML = ''; });

  modal.querySelector('#tplApply').addEventListener('click', () => {
    const sourceDay = modal.querySelector('#templateDaySelect').value;
    const markTplHoliday = modal.querySelector('#markHoliday').checked;
    const markTargetsHoliday = modal.querySelector('#targetHoliday').checked;
    const targetChecks = Array.from(modal.querySelectorAll('input[type=checkbox]')).filter(cb => cb.checked).map(cb => cb.value);
    if (targetChecks.length === 0) { alert('Please select at least one target day to copy to (or choose the same day).'); return; }
    const tplRows = Array.from(tplSlotsDiv.children).map(div => {
      return { start: div.querySelector('.tpl-start').value, end: div.querySelector('.tpl-end').value, type: div.querySelector('.tpl-type').value };
    });

    if (markTplHoliday) addHolidayForDay(sourceDay);
    else tplRows.forEach(slot => addSlotRow('', sourceDay, slot.start, slot.end, slot.type));

    targetChecks.forEach(d => {
      if (markTargetsHoliday) addHolidayForDay(d);
      else tplRows.forEach(slot => addSlotRow('', d, slot.start, slot.end, slot.type));
    });

    modalRoot.innerHTML = '';
    setStatus(`Applied template for ${sourceDay} to ${targetChecks.join(', ')}`);
    setTimeout(updateAllMarkButtons, 60);
  });
}

// ========== RENDER / DOWNLOAD / IMAGE ========== 
// Renders timetable as day × time-range grid using slot_label / start fields.
// Expect assignments items to include: day, slot_label, start, end, course, faculty, slot_index
function renderTimetable(assignments) {
  el('output').classList.remove('hidden');
  const container = el('timetableContainer');
  if (!assignments || assignments.length === 0) {
    container.innerHTML = '<div class="text-sm text-gray-500">No assignments returned.</div>';
    return;
  }

  // Extract unique days and sort them
  const days = [...new Set(assignments.map(a => a.day))].sort((a, b) => {
    const dayOrder = { 'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6 };
    return (dayOrder[a] ?? 99) - (dayOrder[b] ?? 99);
  });

  // Extract unique slot times (start_time) and sort them
  const slotTimes = [...new Set(assignments.map(a => a.start_time))].sort((a, b) => {
    const timeA = timeToMinutes(a);
    const timeB = timeToMinutes(b);
    return (timeA ?? 0) - (timeB ?? 0);
  });

  // Create a grid for easy lookup: grid[day][start_time] = [assignments]
  const grid = {};
  days.forEach(day => {
    grid[day] = {};
    slotTimes.forEach(time => {
      grid[day][time] = [];
    });
  });

  assignments.forEach(a => {
    if (grid[a.day] && grid[a.day][a.start_time]) {
      grid[a.day][a.start_time].push(a);
    }
  });

  // Build HTML table
  let html = '<table class="timetable-card min-w-full text-sm border-collapse border border-gray-200">';
  html += '<thead class="bg-gray-50"><tr class="text-left"><th class="p-2 border-b border-gray-200">Day\Time</th>';
  for (const time of slotTimes) {
    html += `<th class="p-2 border-b border-gray-200">${time}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const day of days) {
    html += `<tr class="border-b border-gray-200 bg-white"><td class="p-2 font-medium">${day}</td>`;
    for (const time of slotTimes) {
      const cells = grid[day][time];
      if (cells && cells.length > 0) {
        // Assuming one assignment per slot for now due to clash penalties
        const cell = cells[0]; 
        html += `<td class="p-2 border-l border-gray-200 slot-cell ${cell.class_type === 'Lab' ? 'lab' : ''}">
          <div class="font-semibold course-code">${cell.course}</div>
          <div class="text-xs text-gray-600 faculty">${cell.faculty || ''}</div>
          <div class="text-xs text-gray-500 room">${cell.room || ''}</div>
        </td>`;
      } else {
        html += `<td class="p-2 border-l border-gray-200 text-gray-400">—</td>`;
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table>';

  container.innerHTML = html;
  el('downloadCsv').onclick = () => downloadCsv(assignments);
  el('startNew').onclick = () => window.location.reload();
}

function downloadCsv(assignments) {
  const header = ['day', 'slot_index', 'start_time', 'end_time', 'course', 'class_type', 'student_group', 'faculty', 'room'];
  const rows = assignments.map(a => [
    a.day,
    a.slot_index,
    a.start_time,
    a.end_time,
    a.course,
    a.class_type,
    a.student_group,
    a.faculty,
    a.room
  ].join(','));
  const csv = [header.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'timetable.csv'; a.click();
  URL.revokeObjectURL(url);
}

async function downloadTimetableImage(filename = 'timetable.png') {
  const container = document.getElementById('timetableContainer');
  if (!container) { setStatus('No timetable to capture', true, false); return; }
  const prevOverflow = container.style.overflow; container.style.overflow = 'visible';
  const isDark = document.documentElement.classList.contains('dark');
  try {
    setStatus('Preparing image...', false, true);
    const canvas = await html2canvas(container, {
      scale: 2,
      useCORS: true,
      backgroundColor: isDark ? '#1f2937' : '#ffffff'
    });
    canvas.toBlob((blob) => {
      if (!blob) { setStatus('Failed to create image', true, false); return; }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url); setStatus('Image downloaded.', false, false);
    }, 'image/png');
  } catch (err) {
    console.error('Capture error:', err);
    setStatus('Error capturing image: ' + err.message, true, false);
  } finally { container.style.overflow = prevOverflow; } 
}
