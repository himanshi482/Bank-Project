/* ==========================================================================
   SPX BANK INVESTMENT PORTAL - INTERACTIVE FRONT-END LOGIC & CALCULATORS
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initPortfolioChart();
    initSipCalculator();
    initNpsCalculator();
    initPpfCalculator();
    initModalHandlers();
});

/* --------------------------------------------------------------------------
   1. PORTFOLIO PERFORMANCE CANVAS CHART
   -------------------------------------------------------------------------- */
const portfolioChartData = {
    '1M': { labels: ['Day 1', 'Day 5', 'Day 10', 'Day 15', 'Day 20', 'Day 25', 'Today'], values: [25000, 25300, 25800, 26100, 26900, 27400, 27850] },
    '3M': { labels: ['May', 'Jun', 'Jul', 'Aug'], values: [22000, 23500, 25100, 27850] },
    '6M': { labels: ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'], values: [20000, 21200, 22800, 24500, 26000, 27850] },
    '1Y': { labels: ['Aug 25', 'Nov 25', 'Feb 26', 'May 26', 'Aug 26'], values: [18000, 20500, 22100, 24800, 27850] },
    '3Y': { labels: ['2023', '2024', '2025', '2026'], values: [12000, 16500, 21000, 27850] },
    '5Y': { labels: ['2021', '2022', '2023', '2024', '2025', '2026'], values: [8000, 11000, 15000, 19500, 23000, 27850] }
};

let currentTf = '1Y';

function initPortfolioChart() {
    const canvas = document.getElementById('portfolioCanvas');
    if (!canvas) return;
    renderCanvasChart('portfolioCanvas', portfolioChartData[currentTf]);
}

function updatePortfolioTimeframe(tf, btn) {
    currentTf = tf;
    document.querySelectorAll('.spx-tf-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderCanvasChart('portfolioCanvas', portfolioChartData[tf]);
}

function renderCanvasChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Handle high DPI crisp drawing
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = rect.height * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

    const width = rect.width;
    const height = rect.height;
    const padding = 40;

    ctx.clearRect(0, 0, width, height);

    const values = data.values;
    const minVal = Math.min(...values) * 0.9;
    const maxVal = Math.max(...values) * 1.1;

    // Draw Grid & Y-Axis Labels
    ctx.strokeStyle = '#e9e1f0';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#6b7280';
    ctx.font = '11px sans-serif';

    const steps = 4;
    for (let i = 0; i <= steps; i++) {
        const y = padding + ((height - 2 * padding) / steps) * i;
        const val = Math.round(maxVal - ((maxVal - minVal) / steps) * i);
        
        ctx.beginPath();
        ctx.moveTo(padding + 10, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();

        ctx.fillText('₹' + val.toLocaleString(), 0, y + 4);
    }

    // Points calculation
    const points = values.map((val, idx) => {
        const x = padding + 20 + ((width - 2 * padding - 30) / (values.length - 1)) * idx;
        const y = height - padding - ((val - minVal) / (maxVal - minVal)) * (height - 2 * padding);
        return { x, y, val, label: data.labels[idx] };
    });

    // Draw Smooth Area Gradient
    const gradient = ctx.createLinearGradient(0, padding, 0, height - padding);
    gradient.addColorStop(0, 'rgba(109, 28, 127, 0.35)');
    gradient.addColorStop(1, 'rgba(109, 28, 127, 0.0)');

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.lineTo(points[points.length - 1].x, height - padding);
    ctx.lineTo(points[0].x, height - padding);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw Chart Line
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.strokeStyle = '#6d1c7f';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw Data Dots & X Labels
    points.forEach((pt) => {
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#6d1c7f';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // X Label
        ctx.fillStyle = '#4b5563';
        ctx.textAlign = 'center';
        ctx.fillText(pt.label, pt.x, height - 12);
    });
}

/* --------------------------------------------------------------------------
   2. SIP CALCULATOR LOGIC
   -------------------------------------------------------------------------- */
function initSipCalculator() {
    const monthlyInput = document.getElementById('sipMonthly');
    const returnInput = document.getElementById('sipReturn');
    const durationInput = document.getElementById('sipDuration');

    if (!monthlyInput || !returnInput || !durationInput) return;

    const updateSip = () => {
        const P = parseFloat(monthlyInput.value);
        const i = parseFloat(returnInput.value) / 12 / 100;
        const n = parseFloat(durationInput.value) * 12;

        document.getElementById('sipMonthlyVal').textContent = '₹' + P.toLocaleString();
        document.getElementById('sipReturnVal').textContent = returnInput.value + '%';
        document.getElementById('sipDurationVal').textContent = durationInput.value + ' Yr';

        const totalInvested = P * n;
        // Compound interest SIP formula: M = P * ({[1 + i]^n - 1} / i) * (1 + i)
        const M = P * ((Math.pow(1 + i, n) - 1) / i) * (1 + i);
        const estimatedReturns = M - totalInvested;

        document.getElementById('sipInvested').textContent = '₹' + Math.round(totalInvested).toLocaleString();
        document.getElementById('sipReturns').textContent = '₹' + Math.round(estimatedReturns).toLocaleString();
        document.getElementById('sipTotal').textContent = '₹' + Math.round(M).toLocaleString();
    };

    monthlyInput.addEventListener('input', updateSip);
    returnInput.addEventListener('input', updateSip);
    durationInput.addEventListener('input', updateSip);

    updateSip();
}

/* --------------------------------------------------------------------------
   3. NPS CALCULATOR LOGIC
   -------------------------------------------------------------------------- */
function initNpsCalculator() {
    const ageInput = document.getElementById('npsAge');
    const monthlyInput = document.getElementById('npsMonthly');
    const returnInput = document.getElementById('npsReturn');

    if (!ageInput || !monthlyInput || !returnInput) return;

    const updateNps = () => {
        const age = parseInt(ageInput.value);
        const P = parseFloat(monthlyInput.value);
        const rate = parseFloat(returnInput.value) / 12 / 100;

        document.getElementById('npsAgeVal').textContent = age + ' Yrs';
        document.getElementById('npsMonthlyVal').textContent = '₹' + P.toLocaleString();
        document.getElementById('npsReturnVal').textContent = returnInput.value + '%';

        const yearsToRetire = Math.max(1, 60 - age);
        const n = yearsToRetire * 12;

        const totalContribution = P * n;
        const corpus = P * ((Math.pow(1 + rate, n) - 1) / rate) * (1 + rate);
        // Assuming 40% annuity for monthly pension with 6% p.a. annuity rate
        const monthlyPension = (corpus * 0.40 * 0.06) / 12;

        document.getElementById('npsTotalContrib').textContent = '₹' + Math.round(totalContribution).toLocaleString();
        document.getElementById('npsCorpus').textContent = '₹' + Math.round(corpus).toLocaleString();
        document.getElementById('npsPension').textContent = '₹' + Math.round(monthlyPension).toLocaleString() + ' / mo';
    };

    ageInput.addEventListener('input', updateNps);
    monthlyInput.addEventListener('input', updateNps);
    returnInput.addEventListener('input', updateNps);

    updateNps();
}

/* --------------------------------------------------------------------------
   4. PPF CALCULATOR LOGIC
   -------------------------------------------------------------------------- */
function initPpfCalculator() {
    const annualInput = document.getElementById('ppfAnnual');
    const durationInput = document.getElementById('ppfDuration');

    if (!annualInput || !durationInput) return;

    const updatePpf = () => {
        const P = parseFloat(annualInput.value);
        const n = parseInt(durationInput.value);
        const r = 0.071; // 7.1% p.a. interest rate for PPF

        document.getElementById('ppfAnnualVal').textContent = '₹' + P.toLocaleString();
        document.getElementById('ppfDurationVal').textContent = n + ' Yrs';

        let totalBalance = 0;
        let totalInvested = P * n;

        for (let i = 0; i < n; i++) {
            totalBalance = (totalBalance + P) * (1 + r);
        }

        const totalInterest = totalBalance - totalInvested;

        document.getElementById('ppfInvested').textContent = '₹' + Math.round(totalInvested).toLocaleString();
        document.getElementById('ppfInterest').textContent = '₹' + Math.round(totalInterest).toLocaleString();
        document.getElementById('ppfMaturity').textContent = '₹' + Math.round(totalBalance).toLocaleString();
    };

    annualInput.addEventListener('input', updatePpf);
    durationInput.addEventListener('input', updatePpf);

    updatePpf();
}

/* --------------------------------------------------------------------------
   5. STEPPER WIZARD FOR NPS / PPF ACCOUNT OPENING
   -------------------------------------------------------------------------- */
let currentWizardStep = 1;

function goToStep(step) {
    if (step < 1 || step > 6) return;

    // Validate current step before proceeding forward
    if (step > currentWizardStep) {
        const stepContainer = document.getElementById(`wizard-step-${currentWizardStep}`);
        if (stepContainer) {
            const inputs = stepContainer.querySelectorAll('input[required], select[required]');
            let isValid = true;
            inputs.forEach(input => {
                if (!validateInput(input)) isValid = false;
            });
            if (!isValid) {
                showToast('Please correct highlighted error fields before proceeding.', 'error');
                return;
            }
        }
    }

    currentWizardStep = step;

    for (let i = 1; i <= 6; i++) {
        const stepEl = document.getElementById(`wizard-step-${i}`);
        const indicator = document.getElementById(`step-indicator-${i}`);
        
        if (stepEl) stepEl.style.display = i === step ? 'block' : 'none';
        if (indicator) {
            indicator.classList.remove('active', 'completed');
            if (i === step) indicator.classList.add('active');
            else if (i < step) indicator.classList.add('completed');
        }
    }
}

/* --------------------------------------------------------------------------
   6. FORM VALIDATION HELPERS
   -------------------------------------------------------------------------- */
function validateInput(input) {
    const val = input.value.trim();
    let isValid = true;

    if (input.hasAttribute('required') && !val) {
        isValid = false;
    } else if (input.dataset.type === 'pan') {
        isValid = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(val.toUpperCase());
    } else if (input.dataset.type === 'aadhaar') {
        isValid = /^\d{12}$/.test(val.replace(/\s+/g, ''));
    } else if (input.dataset.type === 'mobile') {
        isValid = /^[6-9]\d{9}$/.test(val);
    } else if (input.type === 'email') {
        isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
    } else if (input.type === 'number') {
        const num = parseFloat(val);
        const min = input.hasAttribute('min') ? parseFloat(input.getAttribute('min')) : 0;
        if (isNaN(num) || num < min) isValid = false;
    }

    if (isValid) {
        input.classList.remove('is-invalid');
    } else {
        input.classList.add('is-invalid');
    }

    return isValid;
}

/* --------------------------------------------------------------------------
   7. MODAL SYSTEM & CONFIRMATION FLOW WITH OTP/MPIN
   -------------------------------------------------------------------------- */
let pendingActionCallback = null;

function initModalHandlers() {
    document.querySelectorAll('.spx-modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            closeAllModals();
        });
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}

function closeAllModals() {
    document.querySelectorAll('.spx-modal-backdrop').forEach(modal => {
        modal.classList.remove('active');
    });
}

function promptSecurityConfirmation(title, detailsHtml, onConfirm) {
    pendingActionCallback = onConfirm;

    const modalTitle = document.getElementById('securityModalTitle');
    const modalDetails = document.getElementById('securityModalDetails');
    const mpinInput = document.getElementById('securityMpinInput');

    if (modalTitle) modalTitle.textContent = title;
    if (modalDetails) modalDetails.innerHTML = detailsHtml;
    if (mpinInput) mpinInput.value = '';

    openModal('securityConfirmModal');
}

function executeSecurityConfirm() {
    const mpinInput = document.getElementById('securityMpinInput');
    if (!mpinInput || mpinInput.value.length < 4) {
        showToast('Please enter a valid 4-digit MPIN / OTP.', 'error');
        mpinInput.classList.add('is-invalid');
        return;
    }

    closeAllModals();
    showToast('Transaction authenticated successfully!', 'success');
    if (typeof pendingActionCallback === 'function') {
        pendingActionCallback();
        pendingActionCallback = null;
    }
}

/* --------------------------------------------------------------------------
   8. TOAST NOTIFICATION UTILITY
   -------------------------------------------------------------------------- */
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `spx-toast spx-toast-${type}`;
    toast.style.cssText = `
        background: ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#6d1c7f'};
        color: #ffffff;
        padding: 12px 20px;
        border-radius: 10px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        margin-top: 10px;
        font-size: 0.88rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 9999;
        animation: fadeIn 0.3s ease;
    `;
    toast.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            ${type === 'success' ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>'}
        </svg>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
