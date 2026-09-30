from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import json
from pathlib import Path

from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import create_engine, create_sessionmaker, init_db
from app import repository as repo
from app.texts import PRESENT, ABSENT, EXCUSED, stats_block, fmt_date
from app.reports import weekly_period, monthly_period, _child_block

DB_URL = "sqlite+aiosqlite:///attendance.db"
engine = create_engine(DB_URL)
sessionmaker: async_sessionmaker[AsyncSession] = create_sessionmaker(engine)

# Standart ota-ona demo chat ID
DEMO_PARENT_CHAT_ID = 10001


async def populate_sample_data_if_empty(session: AsyncSession) -> None:
    students = await repo.list_students(session)
    if not students:
        samples = [
            "Ali Valiyev",
            "Malika Karimova",
            "Jasur Toshmatov",
            "Zilola Rahimova",
            "Bobur Oripov",
        ]
        created = []
        for name in samples:
            st = await repo.add_student(session, name)
            created.append(st)

        # Ota-onaga dastlabki 2 ta o'quvchini bog'lash
        await repo.link_parent(session, DEMO_PARENT_CHAT_ID, created[0].id)
        await repo.link_parent(session, DEMO_PARENT_CHAT_ID, created[1].id)

        # O'tgan 3 kun uchun namuna davomat
        today = date.today()
        await repo.save_attendance(session, today - timedelta(days=2), {
            created[0].id: PRESENT,
            created[1].id: PRESENT,
            created[2].id: PRESENT,
            created[3].id: PRESENT,
            created[4].id: ABSENT,
        })
        await repo.save_attendance(session, today - timedelta(days=1), {
            created[0].id: PRESENT,
            created[1].id: EXCUSED,
            created[2].id: PRESENT,
            created[3].id: PRESENT,
            created[4].id: PRESENT,
        })
        await repo.save_attendance(session, today, {
            created[0].id: PRESENT,
            created[1].id: PRESENT,
            created[2].id: ABSENT,
            created[3].id: PRESENT,
            created[4].id: PRESENT,
        })


HTML_PAGE = """<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EDU MEMORY — Maktab Davomat Tizimi</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">
  <!-- Top Navigation Bar -->
  <header class="bg-indigo-700 text-white shadow-lg sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex justify-between items-center">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-2xl shadow-inner">
          🎓
        </div>
        <div>
          <h1 class="text-xl font-bold tracking-tight">EDU MEMORY</h1>
          <p class="text-xs text-indigo-200">Maktab davomatini boshqarish va ota-onalar hisobot tizimi</p>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-200 border border-emerald-400/30">
          <span class="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-pulse"></span> HTTP Server Faol
        </span>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full">
    <!-- Stat Summary Badges -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-user-graduate"></i>
        </div>
        <div>
          <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">O'quvchilar</div>
          <div id="statTotalStudents" class="text-2xl font-bold text-slate-800">--</div>
        </div>
      </div>

      <div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-circle-check"></i>
        </div>
        <div>
          <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Bugun Bor</div>
          <div id="statTodayPresent" class="text-2xl font-bold text-emerald-600">--</div>
        </div>
      </div>

      <div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-circle-xmark"></i>
        </div>
        <div>
          <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Bugun Yo'q</div>
          <div id="statTodayAbsent" class="text-2xl font-bold text-rose-600">--</div>
        </div>
      </div>

      <div class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex items-center space-x-4">
        <div class="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-clock"></i>
        </div>
        <div>
          <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Bugun Sababli</div>
          <div id="statTodayExcused" class="text-2xl font-bold text-amber-600">--</div>
        </div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="flex border-b border-slate-200 mb-6 space-x-2">
      <button onclick="switchTab('davomat')" id="tabBtnDavomat" class="px-5 py-3 font-semibold text-sm border-b-2 border-indigo-600 text-indigo-600 flex items-center space-x-2">
        <i class="fa-solid fa-calendar-check"></i>
        <span>Kunlik Davomat</span>
      </button>
      <button onclick="switchTab('students')" id="tabBtnStudents" class="px-5 py-3 font-semibold text-sm border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center space-x-2">
        <i class="fa-solid fa-users"></i>
        <span>O'quvchilar Boshqaruvi</span>
      </button>
      <button onclick="switchTab('parent')" id="tabBtnParent" class="px-5 py-3 font-semibold text-sm border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center space-x-2">
        <i class="fa-solid fa-house-user"></i>
        <span>Ota-ona Kabineti</span>
      </button>
      <button onclick="switchTab('telegram')" id="tabBtnTelegram" class="px-5 py-3 font-semibold text-sm border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center space-x-2">
        <i class="fa-brands fa-telegram"></i>
        <span>Telegram Xabarnoma Ko'rinishi</span>
      </button>
    </div>

    <!-- TAB 1: KUNLIK DAVOMAT -->
    <div id="tabDavomat" class="space-y-4">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center space-x-3">
          <label class="text-sm font-semibold text-slate-700" for="attDate">Sanani tanlang:</label>
          <input type="date" id="attDate" class="border border-slate-200 rounded-xl px-3 py-2 text-sm font-medium focus:ring-2 focus:ring-indigo-500 focus:outline-none" onchange="loadAttendance()">
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="setAllAttendance('present')" class="px-3.5 py-2 text-xs font-semibold rounded-xl bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition">
            🟢 Barchasi Bor
          </button>
          <button onclick="setAllAttendance('absent')" class="px-3.5 py-2 text-xs font-semibold rounded-xl bg-rose-50 text-rose-700 hover:bg-rose-100 transition">
            🔴 Barchasi Yo'q
          </button>
          <button onclick="saveAttendance()" class="px-5 py-2 text-xs font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-100 transition flex items-center space-x-1.5">
            <i class="fa-solid fa-floppy-disk"></i>
            <span>Davomatni Saqlash</span>
          </button>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <table class="min-w-full divide-y divide-slate-100 text-sm">
          <thead class="bg-slate-50 text-slate-500 font-semibold">
            <tr>
              <th class="px-6 py-3.5 text-left">#</th>
              <th class="px-6 py-3.5 text-left">O'quvchi Ism-Familiyasi</th>
              <th class="px-6 py-3.5 text-left">Maxsus ID Kod</th>
              <th class="px-6 py-3.5 text-center">Status</th>
            </tr>
          </thead>
          <tbody id="attendanceTableBody" class="divide-y divide-slate-100">
            <!-- Dynamic rows -->
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 2: O'QUVCHILAR BOSHQARUVI -->
    <div id="tabStudents" class="space-y-4 hidden">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-slate-800">Sinf O'quvchilari Ro'yxati</h2>
          <p class="text-xs text-slate-400">Har bir o'quvchiga ota-onasi ulanishi uchun unikal 6 xonali ID kod beriladi.</p>
        </div>
        <form onsubmit="addStudent(event)" class="flex items-center space-x-2">
          <input type="text" id="newStudentName" required placeholder="O'quvchi to'liq ismi (masalan: Ali Valiyev)" class="border border-slate-200 rounded-xl px-4 py-2 text-sm w-72 focus:ring-2 focus:ring-indigo-500 focus:outline-none">
          <button type="submit" class="px-5 py-2 text-sm font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition">
            ➕ Qo'shish
          </button>
        </form>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <table class="min-w-full divide-y divide-slate-100 text-sm">
          <thead class="bg-slate-50 text-slate-500 font-semibold">
            <tr>
              <th class="px-6 py-3.5 text-left">#</th>
              <th class="px-6 py-3.5 text-left">Ism-Familiya</th>
              <th class="px-6 py-3.5 text-left">Ota-ona uchun ID Kod</th>
              <th class="px-6 py-3.5 text-center">Jami Davomat</th>
              <th class="px-6 py-3.5 text-right">Amallar</th>
            </tr>
          </thead>
          <tbody id="studentsTableBody" class="divide-y divide-slate-100">
            <!-- Dynamic rows -->
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: OTA-ONA KABINETI -->
    <div id="tabParent" class="space-y-6 hidden">
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        <h2 class="text-lg font-bold text-slate-800 mb-1">Ota-ona Profil Simulyatori</h2>
        <p class="text-xs text-slate-400 mb-4">Ota-ona Telegram botda farzandining 6 xonali ID kodini kiritib farzandini o'ziga bog'laydi.</p>
        <form onsubmit="linkParent(event)" class="flex items-center space-x-2 max-w-md">
          <input type="text" id="parentStudentCode" required placeholder="Masalan: Z2YABT" class="border border-slate-200 rounded-xl px-4 py-2 text-sm uppercase tracking-widest font-mono focus:ring-2 focus:ring-indigo-500 focus:outline-none flex-1">
          <button type="submit" class="px-5 py-2 text-sm font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 transition">
            Bog'lash
          </button>
        </form>
      </div>

      <div>
        <h3 class="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3">Bog'langan Farzandlar va Ularning Davomat Ko'rsatkichlari</h3>
        <div id="parentChildrenList" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Dynamic cards -->
        </div>
      </div>
    </div>

    <!-- TAB 4: TELEGRAM XABAR KO'RINIShI -->
    <div id="tabTelegram" class="space-y-6 hidden">
      <div class="max-w-xl mx-auto bg-slate-100 rounded-3xl p-6 shadow-sm border border-slate-200">
        <div class="flex items-center space-x-3 pb-4 mb-4 border-b border-slate-200">
          <div class="w-10 h-10 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold text-lg">
            🤖
          </div>
          <div>
            <div class="font-bold text-slate-800 text-sm">EDU MEMORY Bot</div>
            <div class="text-xs text-blue-600">bot @edu_memory_bot</div>
          </div>
        </div>

        <!-- Telegram Message Bubble -->
        <div class="bg-white rounded-2xl p-4 shadow-sm text-sm border border-slate-200/60 leading-relaxed font-mono whitespace-pre-wrap text-slate-700" id="telegramMessagePreview">
Yuklanmoqda...
        </div>
        <div class="text-[10px] text-right text-slate-400 mt-1">18:00 (Shanba) ✓✓</div>
      </div>
    </div>
  </main>

  <footer class="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
    EDU MEMORY &copy; 2026 — Maktab davomatini boshqarish platformasi
  </footer>

  <script>
    let students = [];
    let attendance = {};

    function switchTab(name) {
      ['davomat', 'students', 'parent', 'telegram'].forEach(t => {
        document.getElementById('tab' + t.charAt(0).toUpperCase() + t.slice(1)).classList.add('hidden');
        const btn = document.getElementById('tabBtn' + t.charAt(0).toUpperCase() + t.slice(1));
        btn.classList.remove('border-indigo-600', 'text-indigo-600');
        btn.classList.add('border-transparent', 'text-slate-500');
      });
      document.getElementById('tab' + name.charAt(0).toUpperCase() + name.slice(1)).classList.remove('hidden');
      const activeBtn = document.getElementById('tabBtn' + name.charAt(0).toUpperCase() + name.slice(1));
      activeBtn.classList.remove('border-transparent', 'text-slate-500');
      activeBtn.classList.add('border-indigo-600', 'text-indigo-600');

      if (name === 'telegram') loadTelegramPreview();
      if (name === 'parent') loadParentChildren();
      if (name === 'students') loadStudents();
    }

    async function init() {
      const today = new Date().toISOString().split('T')[0];
      document.getElementById('attDate').value = today;
      await loadStudents();
      await loadAttendance();
      await updateSummary();
    }

    async function loadStudents() {
      const res = await fetch('/api/students');
      students = await res.json();
      renderStudentsTable();
      renderAttendanceTable();
      document.getElementById('statTotalStudents').innerText = students.length;
    }

    function renderStudentsTable() {
      const tbody = document.getElementById('studentsTableBody');
      tbody.innerHTML = '';
      students.forEach((s, idx) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50/50 transition';
        tr.innerHTML = `
          <td class="px-6 py-4 font-semibold text-slate-400">${idx + 1}</td>
          <td class="px-6 py-4 font-semibold text-slate-800">${s.full_name}</td>
          <td class="px-6 py-4">
            <span class="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
              ${s.student_code}
            </span>
          </td>
          <td class="px-6 py-4 text-center">
            <div class="flex items-center justify-center space-x-2">
              <span class="font-bold text-slate-700">${s.percent}%</span>
              <div class="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div class="bg-emerald-500 h-1.5 rounded-full" style="width: ${s.percent}%"></div>
              </div>
            </div>
          </td>
          <td class="px-6 py-4 text-right">
            <button onclick="deleteStudent(${s.id})" class="text-rose-500 hover:text-rose-700 transition p-1">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function loadAttendance() {
      const dateVal = document.getElementById('attDate').value;
      const res = await fetch(`/api/attendance?date=${dateVal}`);
      attendance = await res.json();
      renderAttendanceTable();
      updateSummary();
    }

    function renderAttendanceTable() {
      const tbody = document.getElementById('attendanceTableBody');
      tbody.innerHTML = '';
      students.forEach((s, idx) => {
        const st = attendance[s.id] || null;
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50/50 transition';
        tr.innerHTML = `
          <td class="px-6 py-4 font-semibold text-slate-400">${idx + 1}</td>
          <td class="px-6 py-4 font-semibold text-slate-800">${s.full_name}</td>
          <td class="px-6 py-4 font-mono text-xs text-slate-500">${s.student_code}</td>
          <td class="px-6 py-4 text-center">
            <div class="inline-flex p-1 bg-slate-100 rounded-xl space-x-1">
              <button onclick="setStatus(${s.id}, 'present')" class="px-3 py-1 rounded-lg text-xs font-semibold transition ${st === 'present' ? 'bg-emerald-500 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200'}">
                🟢 Bor
              </button>
              <button onclick="setStatus(${s.id}, 'absent')" class="px-3 py-1 rounded-lg text-xs font-semibold transition ${st === 'absent' ? 'bg-rose-500 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200'}">
                🔴 Yo'q
              </button>
              <button onclick="setStatus(${s.id}, 'excused')" class="px-3 py-1 rounded-lg text-xs font-semibold transition ${st === 'excused' ? 'bg-amber-500 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-200'}">
                🟡 Sababli
              </button>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function setStatus(sid, val) {
      attendance[sid] = val;
      renderAttendanceTable();
      updateSummary();
    }

    function setAllAttendance(val) {
      students.forEach(s => attendance[s.id] = val);
      renderAttendanceTable();
      updateSummary();
    }

    function updateSummary() {
      let p = 0, a = 0, e = 0;
      students.forEach(s => {
        const st = attendance[s.id];
        if (st === 'present') p++;
        else if (st === 'absent') a++;
        else if (st === 'excused') e++;
      });
      document.getElementById('statTodayPresent').innerText = p;
      document.getElementById('statTodayAbsent').innerText = a;
      document.getElementById('statTodayExcused').innerText = e;
    }

    async function saveAttendance() {
      const dateVal = document.getElementById('attDate').value;
      const res = await fetch('/api/attendance', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({date: dateVal, statuses: attendance})
      });
      if (res.ok) {
        alert("✅ Davomat muvaffaqiyatli saqlandi!");
        loadStudents();
      }
    }

    async function addStudent(e) {
      e.preventDefault();
      const input = document.getElementById('newStudentName');
      const res = await fetch('/api/students', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({full_name: input.value.trim()})
      });
      if (res.ok) {
        input.value = '';
        await loadStudents();
        await loadAttendance();
      }
    }

    async function deleteStudent(id) {
      if (!confirm("O'quvchini ro'yxatdan o'chirishni tasdiqlaysizmi?")) return;
      const res = await fetch(`/api/students/${id}`, {method: 'DELETE'});
      if (res.ok) {
        await loadStudents();
        await loadAttendance();
      }
    }

    async function linkParent(e) {
      e.preventDefault();
      const input = document.getElementById('parentStudentCode');
      const code = input.value.trim().toUpperCase();
      const res = await fetch('/api/parent/link', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code})
      });
      const data = await res.json();
      alert(data.message);
      input.value = '';
      loadParentChildren();
    }

    async function loadParentChildren() {
      const res = await fetch('/api/parent/children');
      const list = await res.json();
      const container = document.getElementById('parentChildrenList');
      container.innerHTML = '';
      if (!list.length) {
        container.innerHTML = '<div class="col-span-2 text-slate-400 text-sm py-4">Hozircha birorta ham farzand bog\'lanmagan. ID kod orqali qo\'shing.</div>';
        return;
      }
      list.forEach(c => {
        const div = document.createElement('div');
        div.className = 'bg-white rounded-2xl p-5 shadow-sm border border-slate-100';
        div.innerHTML = `
          <div class="flex justify-between items-start mb-3">
            <div>
              <h4 class="font-bold text-slate-800 text-base">${c.full_name}</h4>
              <span class="text-xs font-mono text-slate-400">Kod: ${c.student_code}</span>
            </div>
            <span class="px-3 py-1 rounded-full text-xs font-bold ${c.percent >= 80 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}">
              ${c.percent}% Davomat
            </span>
          </div>
          <div class="grid grid-cols-3 gap-2 text-center text-xs mt-3">
            <div class="bg-emerald-50 rounded-xl py-2">
              <div class="text-emerald-700 font-bold text-base">${c.present}</div>
              <div class="text-emerald-600/70">🟢 Bor</div>
            </div>
            <div class="bg-rose-50 rounded-xl py-2">
              <div class="text-rose-700 font-bold text-base">${c.absent}</div>
              <div class="text-rose-600/70">🔴 Yo'q</div>
            </div>
            <div class="bg-amber-50 rounded-xl py-2">
              <div class="text-amber-700 font-bold text-base">${c.excused}</div>
              <div class="text-amber-600/70">🟡 Sababli</div>
            </div>
          </div>
        `;
        container.appendChild(div);
      });
    }

    async function loadTelegramPreview() {
      const res = await fetch('/api/reports/weekly');
      const data = await res.json();
      document.getElementById('telegramMessagePreview').innerText = data.text;
    }

    window.onload = init;
  </script>
</body>
</html>
"""


async def handle_index(_request: web.Request) -> web.Response:
    return web.Response(text=HTML_PAGE, content_type="text/html")


async def handle_get_students(_request: web.Request) -> web.Response:
    async with sessionmaker() as session:
        students = await repo.list_students(session)
        out = []
        for s in students:
            st = await repo.get_stats(session, s.id)
            out.append({
                "id": s.id,
                "full_name": s.full_name,
                "student_code": s.student_code,
                "present": st.present,
                "absent": st.absent,
                "excused": st.excused,
                "total": st.total,
                "percent": round(st.percent, 1),
            })
        return web.json_response(out)


async def handle_add_student(request: web.Request) -> web.Response:
    data = await request.json()
    name = (data.get("full_name") or "").strip()
    if not name:
        return web.json_response({"error": "Ism kiritilmadi"}, status=400)
    async with sessionmaker() as session:
        student = await repo.add_student(session, name)
        return web.json_response({
            "id": student.id,
            "full_name": student.full_name,
            "student_code": student.student_code,
        })


async def handle_delete_student(request: web.Request) -> web.Response:
    sid = int(request.match_info["id"])
    async with sessionmaker() as session:
        ok = await repo.delete_student(session, sid)
        return web.json_response({"ok": ok})


async def handle_get_attendance(request: web.Request) -> web.Response:
    date_str = request.query.get("date")
    day = date.fromisoformat(date_str) if date_str else date.today()
    async with sessionmaker() as session:
        att = await repo.get_attendance_map(session, day)
        return web.json_response(att)


async def handle_save_attendance(request: web.Request) -> web.Response:
    data = await request.json()
    day = date.fromisoformat(data["date"])
    statuses = {int(k): v for k, v in data.get("statuses", {}).items()}
    async with sessionmaker() as session:
        count = await repo.save_attendance(session, day, statuses)
        return web.json_response({"saved_count": count})


async def handle_link_parent(request: web.Request) -> web.Response:
    data = await request.json()
    code = (data.get("code") or "").strip()
    async with sessionmaker() as session:
        student = await repo.get_student_by_code(session, code)
        if not student:
            return web.json_response({"success": False, "message": "❌ Bunday kodli o'quvchi topilmadi!"})
        linked = await repo.link_parent(session, DEMO_PARENT_CHAT_ID, student.id)
        if linked:
            return web.json_response({"success": True, "message": f"✅ {student.full_name} muvaffaqiyatli bog'landi!"})
        return web.json_response({"success": False, "message": f"ℹ️ {student.full_name} allaqachon bog'langan!"})


async def handle_parent_children(_request: web.Request) -> web.Response:
    async with sessionmaker() as session:
        children = await repo.get_children(session, DEMO_PARENT_CHAT_ID)
        out = []
        for c in children:
            st = await repo.get_stats(session, c.id)
            out.append({
                "id": c.id,
                "full_name": c.full_name,
                "student_code": c.student_code,
                "present": st.present,
                "absent": st.absent,
                "excused": st.excused,
                "percent": round(st.percent, 1),
            })
        return web.json_response(out)


async def handle_weekly_report(_request: web.Request) -> web.Response:
    today = date.today()
    w_start, w_end, _ = weekly_period(today)
    async with sessionmaker() as session:
        children = await repo.get_children(session, DEMO_PARENT_CHAT_ID)
        blocks = []
        for c in children:
            st = await repo.get_stats(session, c.id, w_start, w_end)
            blocks.append(_child_block(c.full_name, st.present, st.absent, st.excused, st.percent))
        text = (
            "📊 EDU MEMORY\\n"
            f"📅 Haftalik davomat hisoboti\\n"
            f"🗓 {fmt_date(w_start)} — {fmt_date(w_end)}\\n\\n" + "\\n\\n".join(blocks)
        )
        return web.json_response({"text": text.replace("<b>", "").replace("</b>", "")})


async def create_app() -> web.Application:
    await init_db(engine)
    async with sessionmaker() as session:
        await populate_sample_data_if_empty(session)

    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/students", handle_get_students)
    app.router.add_post("/api/students", handle_add_student)
    app.router.add_delete("/api/students/{id}", handle_delete_student)
    app.router.add_get("/api/attendance", handle_get_attendance)
    app.router.add_post("/api/attendance", handle_save_attendance)
    app.router.add_post("/api/parent/link", handle_link_parent)
    app.router.add_get("/api/parent/children", handle_parent_children)
    app.router.add_get("/api/reports/weekly", handle_weekly_report)
    return app


if __name__ == "__main__":
    app = asyncio.run(create_app())
    web.run_app(app, host="127.0.0.1", port=5000)
