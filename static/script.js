// Admin - Editace uživatele
function editUser(user) {
    document.getElementById('editForm').action = `/admin/user/edit/${user.id}`;
    document.getElementById('edit_name').value = user.name;
    document.getElementById('edit_login').value = user.login;
    document.getElementById('edit_key').value = user.key;
    document.getElementById('edit_school').value = user.school;
    document.getElementById('edit_role').value = user.role;
    document.getElementById('edit_password').value = '';
    
    // Nastavit checkboxy
    document.getElementById('edit_perm_ps').checked = user.permissions.includes('Photoshop');
    document.getElementById('edit_perm_ai').checked = user.permissions.includes('Illustrator');
    document.getElementById('edit_perm_bl').checked = user.permissions.includes('Blender');
    
    document.getElementById('editModal').style.display = 'block';
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

// Nové: naplnění modalu z data-* atributů tlačítka
function editUserFromDataset(btn) {
    const perms = (btn.dataset.permissions || '').split('|').filter(Boolean);
    const user = {
        id: parseInt(btn.dataset.id, 10),
        name: btn.dataset.name || '',
        login: btn.dataset.login || '',
        key: btn.dataset.key || '',
        school: btn.dataset.school || '',
        role: btn.dataset.role || 'hodnotitel',
        permissions: perms
    };
    editUser(user);
}

// Správa kritérií
function openAddCriterionModal(category) {
    document.getElementById('criterion_category').value = category;
    document.getElementById('criterion_name').value = '';
    document.getElementById('criterion_type').value = 'slider';
    document.getElementById('criterion_min').value = 0;
    document.getElementById('criterion_max').value = 10;
    toggleSliderOptions();
    document.getElementById('criterionModal').style.display = 'block';
}

function closeCriterionModal() {
    document.getElementById('criterionModal').style.display = 'none';
}

function openDeleteEvaluationsModal() {
    document.getElementById('confirmDeleteCheckbox').checked = false;
    document.getElementById('admin_password_confirm').value = '';
    document.getElementById('deleteEvaluationsModal').style.display = 'block';
}

function closeDeleteEvaluationsModal() {
    document.getElementById('deleteEvaluationsModal').style.display = 'none';
}

function validateDeleteEvaluations() {
    const checkbox = document.getElementById('confirmDeleteCheckbox');
    const password = document.getElementById('admin_password_confirm').value;
    
    if (!checkbox.checked) {
        alert('Musíte potvrdit, že rozumíte důsledkům této akce.');
        return false;
    }
    
    if (!password || password.trim() === '') {
        alert('Musíte zadat heslo pro potvrzení.');
        return false;
    }
    
    return confirm('Opravdu chcete smazat VŠECHNA hodnocení? Tato akce je NEVRATNÁ!');
}

function toggleSliderOptions() {
    const type = document.getElementById('criterion_type').value;
    const sliderOptions = document.getElementById('slider_options');
    if (type === 'slider') {
        sliderOptions.style.display = 'block';
    } else {
        sliderOptions.style.display = 'none';
    }
}

// Hodnocení - update slider values
function updateSliderValue(criterionId, min, max) {
    const value = document.getElementById('criterion_' + criterionId).value;
    document.getElementById('value_' + criterionId).textContent = value;
}

// Zobrazení obrázku v modalu
function viewImage(imageUrl) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    
    modal.style.display = 'block';
    modalImg.src = imageUrl;
}

function closeImageModal() {
    document.getElementById('imageModal').style.display = 'none';
}

function renderPendingReports(reports) {
    const list = document.getElementById('pendingReportsList');
    if (!list) {
        return;
    }

    if (!reports || reports.length === 0) {
        list.innerHTML = '<p class="refresh-info" id="noPendingReports">Žádná čekající hlášení.</p>';
        return;
    }

    const html = reports.map(report => {
        const note = report.note
            ? `<div class="report-note">Poznámka: ${report.note}</div>`
            : '';
        return `
            <div class="report-item">
                <div>
                    <strong>${report.evaluator_name}</strong> nahlásil(a) nepřesnost u práce <strong>${report.creation_name}</strong>.
                    ${note}
                </div>
                <form method="POST" action="/admin/reports/resolve/${report.id}">
                    <button type="submit" class="btn btn-success btn-sm">Označit jako vyřešené</button>
                </form>
            </div>
        `;
    }).join('');

    list.innerHTML = html;
}

function startAdminLiveUpdates() {
    const pendingEl = document.getElementById('pendingReportsCount');

    if (!pendingEl || !window.liveStatsUrl) {
        return;
    }

    const refresh = () => {
        fetch(window.liveStatsUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Nepodařilo se načíst živá data.');
                }
                return response.json();
            })
            .then(data => {
                pendingEl.textContent = data.pending_reports_count;
                renderPendingReports(data.pending_reports || []);
            })
            .catch(() => {
            });
    };

    refresh();
    setInterval(refresh, 5000);
}

// Zavření modalu kliknutím mimo obsah
window.onclick = function(event) {
    const editModal = document.getElementById('editModal');
    const criterionModal = document.getElementById('criterionModal');
    const imageModal = document.getElementById('imageModal');
    const deleteEvaluationsModal = document.getElementById('deleteEvaluationsModal');
    
    if (editModal && event.target == editModal) {
        closeEditModal();
    }
    if (criterionModal && event.target == criterionModal) {
        closeCriterionModal();
    }
    if (imageModal && event.target == imageModal) {
        closeImageModal();
    }
    if (deleteEvaluationsModal && event.target == deleteEvaluationsModal) {
        closeDeleteEvaluationsModal();
    }
}

// Automatické převedení klíče na velká písmena
document.addEventListener('DOMContentLoaded', function() {
    const keyInputs = document.querySelectorAll('input[name="key"]');
    keyInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    });
    
    // Cursor glow: update CSS variables for mouse position
    document.addEventListener('mousemove', (e) => {
        const x = e.clientX + 'px';
        const y = e.clientY + 'px';
        document.documentElement.style.setProperty('--mx', x);
        document.documentElement.style.setProperty('--my', y);
    });

    // Tilt effect for interactive cards
    const tiltSelectors = [
        '.creation-card', '.stat-card'
    ];
    const tiltElems = document.querySelectorAll(tiltSelectors.join(','));

    tiltElems.forEach(el => {
        el.classList.add('tilt');
        const scale = 1.005;
        const maxDeg = 3;
        function handleMove(e) {
            const rect = el.getBoundingClientRect();
            const cx = e.clientX - rect.left;
            const cy = e.clientY - rect.top;
            const rx = ((cy / rect.height) - 0.5) * -2 * maxDeg;
            const ry = ((cx / rect.width) - 0.5) * 2 * maxDeg;
            el.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) scale(${scale})`;
        }
        function reset() {
            el.style.transform = '';
        }
        el.addEventListener('mousemove', handleMove);
        el.addEventListener('mouseleave', reset);
    });

    // Button ripple enhancement tied to CSS variable --mx/--my already
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('mouseenter', () => {
            btn.style.willChange = 'transform';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.willChange = 'auto';
        });
    });

    startAdminLiveUpdates();
});
