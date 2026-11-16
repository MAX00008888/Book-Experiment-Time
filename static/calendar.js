(() => {
  'use strict';
  const slots = JSON.parse(document.getElementById('slot-data').textContent);
  const daysHeader = document.getElementById('calendar-days');
  const dayColumns = document.getElementById('day-columns');
  const hourLabels = document.getElementById('hour-labels');
  const rangeLabel = document.getElementById('week-range');
  const selectedLabel = document.getElementById('selected');
  const slotField = document.getElementById('slot_id');
  const submit = document.getElementById('submit-booking');
  const today = new Date();
  // Date parts use local calendar dates, but the event timestamps are wall-clock strings in the research timezone.
  const dayKey = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const fromKey = key => new Date(`${key}T12:00:00`);
  const plusDays = (d, days) => { const x = new Date(d); x.setDate(x.getDate()+days); return x; };
  const weekStart = d => plusDays(d, -d.getDay());
  let firstDay = weekStart(today);
  let selectedId = null;
  const minutes = hm => Number(hm.substring(0,2))*60 + Number(hm.substring(3,5));
  const fmt = hm => { const h=Number(hm.substring(0,2)), m=hm.substring(3,5); return `${h%12 || 12}:${m} ${h<12?'AM':'PM'}`; };
  const sameDay = (d, key) => dayKey(d) === key;
  const allHours = slots.flatMap(s => [minutes(s.starts_at.slice(11)), minutes(s.ends_at.slice(11))]);
  const startHour = allHours.length ? Math.max(0, Math.floor(Math.min(...allHours)/60)) : 8;
  const endHour = allHours.length ? Math.min(24, Math.ceil(Math.max(...allHours)/60)) : 18;
  const hours = Math.max(1, endHour-startHour);
  const hourHeight = 78;
  function choose(s, btn) {
    selectedId = s.id;
    slotField.value = String(s.id);
    submit.disabled = false;
    selectedLabel.textContent = `${s.starts_at.slice(0,10)} · ${fmt(s.starts_at.slice(11))} – ${fmt(s.ends_at.slice(11))}`;
    document.querySelectorAll('.session-block.selected').forEach(el => el.classList.remove('selected'));
    btn.classList.add('selected');
  }
  function render() {
    const last = plusDays(firstDay,6);
    const fmtRange = {month:'short', day:'numeric'};
    rangeLabel.textContent = `${firstDay.toLocaleDateString('en-CA',fmtRange)} – ${last.toLocaleDateString('en-CA',{...fmtRange, year:'numeric'})}`;
    daysHeader.replaceChildren(); dayColumns.replaceChildren(); hourLabels.replaceChildren();
    const corner = document.createElement('div'); corner.className='calendar-corner'; daysHeader.append(corner);
    for(let i=0;i<=hours;i++) {
      const lab = document.createElement('span'); lab.textContent=`${(startHour+i)%12||12} ${(startHour+i)<12?'AM':'PM'}`; lab.style.top=`${i*hourHeight}px`; hourLabels.append(lab);
    }
    let visible = 0;
    for (let d=0; d<7; d++) {
      const date=plusDays(firstDay,d), key=dayKey(date);
      const heading=document.createElement('div');heading.className='calendar-day-head'+(sameDay(today,key)?' is-today':'');
      const n=document.createElement('strong');n.textContent=String(date.getDate());
      const name=document.createElement('span');name.textContent=date.toLocaleDateString('en-CA',{weekday:'short'});
      heading.append(n,name); daysHeader.append(heading);
      const col=document.createElement('div'); col.className='calendar-day-column';col.style.height=`${hours*hourHeight}px`;
      slots.filter(s=>s.starts_at.slice(0,10)===key).forEach(s=>{
        const el=document.createElement(s.available?'button':'div');
        const top=(minutes(s.starts_at.slice(11))-startHour*60)/60*hourHeight;
        const height=(minutes(s.ends_at.slice(11))-minutes(s.starts_at.slice(11)))/60*hourHeight;
        el.className=`session-block ${s.available?'free':'reserved'}${selectedId===s.id?' selected':''}`;
        el.style.top=`${Math.max(0,top)}px`;el.style.height=`${Math.max(20,height)}px`;
        const time=document.createElement('strong');time.textContent=`${fmt(s.starts_at.slice(11))} – ${fmt(s.ends_at.slice(11))}`;
        const detail=document.createElement('span');detail.textContent=s.available?'Available · Select':'Booked';el.append(time,detail);
        if(s.available){el.type='button';el.setAttribute('aria-label',`${key}, ${time.textContent}, available`);el.addEventListener('click',()=>choose(s,el));visible++;}
        col.append(el);
      });dayColumns.append(col);
    }
    document.getElementById('available-count').textContent=`${visible} available this week`;
  }
  document.getElementById('prev-week').addEventListener('click',()=>{firstDay=plusDays(firstDay,-7);render()});
  document.getElementById('next-week').addEventListener('click',()=>{firstDay=plusDays(firstDay,7);render()});
  document.getElementById('today-week').addEventListener('click',()=>{firstDay=weekStart(today);render()});
  document.getElementById('booking-form').addEventListener('submit', e=>{if(!slotField.value){e.preventDefault();alert('Please choose an available session from the calendar.')}});
  // Open on the first available future week if the current week has no sessions.
  const future = slots.find(s=>s.available);
  if(future && !slots.some(s=>s.available && s.starts_at.slice(0,10)>=dayKey(firstDay) && s.starts_at.slice(0,10)<=dayKey(plusDays(firstDay,6)))) firstDay=weekStart(fromKey(future.starts_at.slice(0,10)));
  render();
})();
