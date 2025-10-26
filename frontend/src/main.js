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
    if (subheading) subheading.innerText = 'Enter data manually for courses, faculty, and slots. Click Generate.';
  } else {
    manualArea.classList.add('hidden');
    uploadForm.classList.remove('hidden');
    if (subheading) subheading.innerText = 'Upload 3 CSV files (courses, faculty, slots) or enter data manually. Click Generate.';
  }
}

// ---------- Row builders ---------- 
function addCourseRow(code = '', title = '', hours = '') {
  const tbody = el('coursesTable').querySelector('tbody');
  const tr = document.createElement('tr');
  tr.className = 'bg-white dark:bg-gray-800 border-b dark:border-gray-700'
  tr.appendChild(createCell(`<input aria-label="Course code" placeholder="CS101" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md" value="${code}">`));
  tr.appendChild(createCell(`<input aria-label="Course title" placeholder="Data Structures" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md" value="${title}">`));
  tr.appendChild(createCell(`<input aria-label="Weekly hours" placeholder="1" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md" type="number" min="1" value="${hours || 1}">`));
  tr.appendChild(createCell(`<button type="button" class="remove-row text-sm px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded">Remove</button>`));
  tbody.appendChild(tr);

  tr.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', realtimeValidate);
  });
  realtimeValidate();
}

function addFacultyRow(initials = '', fullname = '', can_teach = '') {
  const tbody = el('facultyTable').querySelector('tbody');
  const tr = document.createElement('tr');
  tr.className = 'bg-white dark:bg-gray-800 border-b dark:border-gray-700'
  tr.appendChild(createCell(`<input aria-label="Faculty initials" placeholder="PR" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md" value="${initials}">`));
  tr.appendChild(createCell(`<input aria-label="Faculty full name" placeholder="Prof Rao" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md" value="${fullname}">`));
  tr.appendChild(createCell(`<input aria-label="Can teach (comma-separated codes)" placeholder="CS101,CS102" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md" value="${can_teach}">`));
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
  tr.className = 'bg-white dark:bg-gray-800'

  tr.appendChild(createCell(`<input aria-label="Day" placeholder="Mon" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md slot-day" value="${day}">`));
  tr.appendChild(createCell(`<input aria-label="Start time" type="time" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md slot-start" value="${start_time}">`));
  tr.appendChild(createCell(`<input aria-label="End time" type="time" class="w-full text-sm p-1 bg-gray-50 border border-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white rounded-md slot-end" value="${end_time}">`));
  tr.appendChild(createCell(`<select aria-label="Slot type" class="w-full text-sm p-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md slot-type">
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
  const allCourseRows = Array.from(el('coursesTable').querySelectorAll('tbody tr'));

  allCourseRows.forEach((r, i) => {
    const inputs = r.querySelectorAll('input');
    const codeInput = inputs[0];
    const titleInput = inputs[1];
    const hoursInput = inputs[2];

    const code = codeInput.value.trim();
    const title = titleInput.value.trim();
    const hours = hoursInput.value.trim();

    // Code validation
    const isDuplicate = allCourseRows.some((otherRow, otherIdx) => otherIdx !== i && otherRow.querySelector('input').value.trim() === code);
    codeInput.classList.toggle('input-error', !code || isDuplicate);
    if (code) courseCodes.add(code);

    // Title validation
    titleInput.classList.toggle('input-error', !title);

    // Hours validation
    hoursInput.classList.toggle('input-error', !hours || parseInt(hours) < 1);
  });

  const facultyRows = Array.from(el('facultyTable').querySelectorAll('tbody tr'));
  facultyRows.forEach((r) => {
    const inputs = r.querySelectorAll('input');
    const initialsInput = inputs[0];
    const nameInput = inputs[1];
    const canTeachInput = inputs[2];

    initialsInput.classList.toggle('input-error', !initialsInput.value.trim());
    nameInput.classList.toggle('input-error', !nameInput.value.trim());

    const canTeachCodes = canTeachInput.value.split(',').map(s => s.trim()).filter(Boolean);
    const allCodesExist = canTeachCodes.every(code => courseCodes.has(code));
    canTeachInput.classList.toggle('input-error', canTeachCodes.length > 0 && !allCodesExist);
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

// ========== MAIN DOM READY / EVENT WIRING ========== 
document.addEventListener('DOMContentLoaded', () => {
  // File input handlers
  handleFileInput('courses', 'courses-filename');
  handleFileInput('faculty', 'faculty-filename');
  handleFileInput('slots', 'slots-filename');

  // add-row handlers
  el('addCourse').addEventListener('click', () => addCourseRow());
  el('addFaculty').addEventListener('click', () => addFacultyRow());
  el('addSlot').addEventListener('click', () => addSlotRow());

  // open modal builder
  el('addCommonDay').addEventListener('click', openCommonDayBuilder);

  // initial rows
  if (el('coursesTable').querySelector('tbody').children.length === 0) addCourseRow();
  if (el('facultyTable').querySelector('tbody').children.length === 0) addFacultyRow();
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
      const coursesCsv = "code,title,weekly_hours\nCS101,Data Structures,3\nCS102,Database Systems,3\nCS103,Operating Systems,3\n";
      const facultyCsvManual = "initials,name,can_teach\nPR,Prof Rao,CS101|CS103\nPP,Prof Patil,CS102\n";
      const slotsCsvManual = "day,start_time,end_time,type\nMon,09:00,10:00,Class\nMon,10:00,11:00,Class\nMon,11:00,11:30,Break\nMon,11:30,12:30,Class\nTue,09:00,10:00,Class\nTue,10:00,11:00,Class\n";

      if (el('modeManual').checked) {
        el('coursesTable').querySelector('tbody').innerHTML = '';
        el('facultyTable').querySelector('tbody').innerHTML = '';
        el('slotsTable').querySelector('tbody').innerHTML = '';

        coursesCsv.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addCourseRow(parts[0]?.trim(), parts[1]?.trim(), parts[2]?.trim());
        });

        facultyCsvManual.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addFacultyRow(parts[0]?.trim(), parts[1]?.trim(), (parts[2] || '').replace(/\|/g, ','));
        });

        slotsCsvManual.split('\n').slice(1).filter(Boolean).forEach(line => {
          const parts = line.split(',');
          addSlotRow('', parts[0]?.trim(), parts[1]?.trim(), parts[2]?.trim(), parts[3]?.trim());
        });

        setStatus('Sample manual data loaded. Edit if needed and click Generate.');
        setTimeout(updateAllMarkButtons, 50);
        return;
      }

      // upload mode sample
      const coursesInput = el('courses');
      const facultyInput = el('faculty');
      const slotsInput = el('slots');

      const faculty = "id,name,can_teach\nf1,Prof Rao,CS101|CS103\nf2,Prof Patil,CS102\n";
      const slots = "id,day,slot_index\nmon-0,Mon,0\nmon-1,Mon,1\ntue-0,Tue,0\ntue-1,Tue,1\n";
      coursesInput.files = fileFromString(coursesCsv, 'courses.csv');
      facultyInput.files = fileFromString(faculty, 'faculty.csv');
      slotsInput.files = fileFromString(slots, 'slots.csv');
      
      // Manually trigger change event to update filename display
      coursesInput.dispatchEvent(new Event('change'));
      facultyInput.dispatchEvent(new Event('change'));
      slotsInput.dispatchEvent(new Event('change'));

      setStatus('Sample data loaded in inputs. Click Generate.');
    } catch (err) {
      console.error('Sample button error', err);
      setStatus('Error preparing sample data: ' + (err && err.message), true, false);
    }
  });

  // generate button wiring (preserve previous logic)
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
          const lines = ['code,title,weekly_hours'];
          for (const r of rows) {
            const inputs = r.querySelectorAll('input');
            const code = (inputs[0]?.value || '').trim();
            const title = (inputs[1]?.value || '').trim();
            const hours = (inputs[2]?.value || '1').trim();
            if (!code) continue;
            lines.push(`${code.replace(/,/g, '')},${title.replace(/,/g, '')},${hours}`);
          }
          return lines.join('\n');
        }

        function serializeFaculty() {
          const rows = Array.from(el('facultyTable').querySelectorAll('tbody tr'));
          if (rows.length === 0) return null;
          const lines = ['id,name,can_teach'];
          let idx = 1;
          for (const r of rows) {
            const inputs = r.querySelectorAll('input');
            const initials = (inputs[0]?.value || '').trim();
            const name = (inputs[1]?.value || '').trim();
            const canTeachRaw = (inputs[2]?.value || '').trim();
            const canTeach = canTeachRaw.split(',').map(s => s.trim()).filter(Boolean).join('|');
            if (!initials && !name) continue;
            let id = initials ? initials.replace(/\s+/g, '_') : `f${idx}`;
            id = id.toLowerCase();
            id = id.replace(/,/g, '');
            lines.push(`${id},${name.replace(/,/g, '')},${canTeach}`);
            idx++;
          }
          return lines.join('\n');
        }

        function serializeSlots() {
          const rows = Array.from(el('slotsTable').querySelectorAll('tbody tr'));
          if (rows.length === 0) return null;
          const lines = ['id,day,slot_index'];
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
            let idx = 0;
            for (const block of dayGroups[day]) {
              if (block.type === 'Class') {
                const slotId = `${day.toLowerCase()}-${idx}`;
                lines.push(`${slotId},${day},${idx}`);
                idx++;
              }
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



          fd.append('courses', stringToFile(coursesCsv, 'courses.csv'));
          fd.append('faculty', stringToFile(facultyCsv, 'faculty.csv'));
          fd.append('slots', stringToFile(slotsCsv, 'slots.csv'));
        } else {
          const courses = el('courses').files[0];
          const faculty = el('faculty').files[0];
          const slots = el('slots').files[0];

          if (!courses || !faculty || !slots) {
            setStatus('Please attach all three CSV files (courses, faculty, slots) or switch to manual entry.', true, false);
            generateBtn.disabled = false;
            return;
          }

          fd.append('courses', courses);
          fd.append('faculty', faculty);
          fd.append('slots', slots);
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
        try { generateBtn.disabled = false; } catch (e) {}
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
      <div><button id="closeCommonDay" class="px-2 py-1 rounded bg-gray-100 dark:bg-gray-600 dark:hover:bg-gray-500 btn-small">Close</button></div>
    </div>
    <div class="space-y-3">
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-sm">Template Day (source)</label>
          <select id="templateDaySelect" class="w-full p-2 border rounded bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600">
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
          <button id="tplClear" class="ml-2 px-3 py-1 bg-gray-100 dark:bg-gray-600 dark:hover:bg-gray-500 rounded btn-small">Clear template</button>
        </div>
        <div class="text-xs text-gray-500 dark:text-gray-400 mt-2">Use time pickers for start/end. Template entries define slots that will be applied to the selected target days.</div>
      </div>

      <div class="mt-4 flex justify-end gap-2">
        <button id="tplApply" class="px-4 py-2 bg-indigo-600 text-white rounded">Apply to selected days</button>
        <button id="tplCancel" class="px-4 py-2 bg-gray-100 dark:bg-gray-600 dark:hover:bg-gray-500 rounded">Cancel</button>
      </div>
    </div>
  `;

  backdrop.appendChild(modal); modalRoot.appendChild(backdrop);

  const tplSlotsDiv = modal.querySelector('#templateSlots');
  function createTemplateSlotRow(start = '09:00', end = '10:00', type = 'Class') {
    const div = document.createElement('div'); div.className = 'flex gap-2 items-center';
    div.innerHTML = `
      <input type="time" class="tpl-start p-1 border rounded bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600" value="${start}">
      <input type="time" class="tpl-end p-1 border rounded bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600" value="${end}">
      <select class="tpl-type p-1 border rounded bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600">
        <option ${type==='Class'? 'selected':''}>Class</option>
        <option ${type==='Break'? 'selected':''}>Break</option>
        <option ${type==='Lunch'? 'selected':''}>Lunch</option>
        <option ${type==='Holiday'? 'selected':''}>Holiday</option>
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
function renderTimetable(assignments) {
  el('output').classList.remove('hidden');
  const container = el('timetableContainer');
  if (!assignments || assignments.length === 0) {
    container.innerHTML = '<div class="text-sm text-gray-500 dark:text-gray-400">No assignments returned.</div>';
    return;
  }
  const days = [...new Set(assignments.map(a => a.day))].sort();
  const maxSlot = Math.max(...assignments.map(a => a.slot_index));
  let html = '<table class="min-w-full text-sm border-collapse border border-gray-200 dark:border-gray-600">';
  html += '<thead class="bg-gray-50 dark:bg-gray-700"><tr class="text-left"><th class="p-2 border-b border-gray-200 dark:border-gray-600">Slot\\Day</th>';
  for (const d of days) html += `<th class="p-2 border-b border-gray-200 dark:border-gray-600">${d}</th>`;
  html += '</tr></thead><tbody>';
  for (let s = 0; s <= maxSlot; s++) {
    html += `<tr class="border-b border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800"><td class="p-2 font-medium">Slot ${s + 1}</td>`;
    for (const d of days) {
      const cell = assignments.find(a => a.day === d && a.slot_index === s);
      if (cell) {
        html += `<td class="p-2 border-l border-gray-200 dark:border-gray-600 slot-cell">
          <div class="font-semibold">${cell.course}</div>
          <div class="text-xs text-gray-600 dark:text-gray-400">${cell.faculty}</div>
        </td>`;
      } else {
        html += `<td class="p-2 border-l border-gray-200 dark:border-gray-600 text-gray-400">—</td>`;
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
  const header = ['day', 'slot_index', 'course', 'faculty'];
  const rows = assignments.map(a => [a.day, a.slot_index, a.course, a.faculty].join(','));
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
