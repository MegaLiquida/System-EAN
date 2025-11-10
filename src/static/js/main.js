// ============================================================================
// JAVASCRIPT PRINCIPAL - SISTEMA DE GESTÃO DE MERCADO
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Sistema de Gestão de Mercado carregado');
    
    // Inicializar tooltips do Bootstrap
    initializeTooltips();
    
    // Inicializar popovers do Bootstrap
    initializePopovers();
});

// ============================================================================
// TOOLTIPS
// ============================================================================

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// ============================================================================
// POPOVERS
// ============================================================================

function initializePopovers() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// ============================================================================
// FORMATAÇÃO
// ============================================================================

function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

function formatDate(date) {
    return new Intl.DateTimeFormat('pt-BR').format(new Date(date));
}

function formatDateTime(date) {
    return new Intl.DateTimeFormat('pt-BR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(date));
}

// ============================================================================
// VALIDAÇÃO DE FORMULÁRIOS
// ============================================================================

function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    return form.checkValidity() === false ? false : true;
}

// ============================================================================
// REQUISIÇÕES AJAX
// ============================================================================

async function fetchAPI(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Erro na requisição:', error);
        throw error;
    }
}

// ============================================================================
// NOTIFICAÇÕES
// ============================================================================

function showNotification(message, type = 'info') {
    const alertClass = `alert-${type}`;
    const alertHTML = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const container = document.querySelector('.container-fluid');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHTML);
    }
}

// ============================================================================
// TABELAS
// ============================================================================

function initializeDataTable(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    // Adicionar funcionalidades básicas à tabela
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        row.addEventListener('click', function() {
            this.classList.toggle('table-active');
        });
    });
}

// ============================================================================
// MODAIS
// ============================================================================

function openModal(modalId) {
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
}

function closeModal(modalId) {
    const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
    if (modal) {
        modal.hide();
    }
}

// ============================================================================
// CONFIRMAÇÃO DE AÇÕES
// ============================================================================

function confirmAction(message = 'Tem certeza que deseja continuar?') {
    return confirm(message);
}

// ============================================================================
// EXPORTAÇÃO DE DADOS
// ============================================================================

function exportTableToCSV(tableId, filename = 'export.csv') {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
        const cols = row.querySelectorAll('td, th');
        const csvRow = [];
        cols.forEach(col => {
            csvRow.push('"' + col.innerText + '"');
        });
        csv.push(csvRow.join(','));
    });
    
    downloadCSV(csv.join('\n'), filename);
}

function downloadCSV(csv, filename) {
    const csvFile = new Blob([csv], { type: 'text/csv' });
    const downloadLink = document.createElement('a');
    downloadLink.href = URL.createObjectURL(csvFile);
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

// ============================================================================
// BUSCA EM TEMPO REAL
// ============================================================================

function setupLiveSearch(inputId, tableId) {
    const input = document.getElementById(inputId);
    const table = document.getElementById(tableId);
    
    if (!input || !table) return;
    
    input.addEventListener('keyup', function() {
        const filter = this.value.toUpperCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const text = row.innerText.toUpperCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
    });
}

// ============================================================================
// PAGINAÇÃO
// ============================================================================

function setupPagination(tableId, itemsPerPage = 10) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const rows = table.querySelectorAll('tbody tr');
    const pages = Math.ceil(rows.length / itemsPerPage);
    
    // Implementar paginação básica
    for (let i = 0; i < rows.length; i++) {
        rows[i].style.display = i < itemsPerPage ? '' : 'none';
    }
}

// ============================================================================
// MÁSCARAS DE ENTRADA
// ============================================================================

function setupInputMasks() {
    // Máscara para CPF
    const cpfInputs = document.querySelectorAll('[data-mask="cpf"]');
    cpfInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.replace(/\D/g, '').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2');
        });
    });
    
    // Máscara para Telefone
    const phoneInputs = document.querySelectorAll('[data-mask="phone"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.replace(/\D/g, '').replace(/(\d{2})(\d)/, '($1) $2').replace(/(\d{5})(\d)/, '$1-$2');
        });
    });
    
    // Máscara para CEP
    const cepInputs = document.querySelectorAll('[data-mask="cep"]');
    cepInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.replace(/\D/g, '').replace(/(\d{5})(\d)/, '$1-$2');
        });
    });
}

// ============================================================================
// DARK MODE (Opcional)
// ============================================================================

function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

function initializeDarkMode() {
    if (localStorage.getItem('darkMode') === 'true') {
        document.body.classList.add('dark-mode');
    }
}

// ============================================================================
// INICIALIZAÇÃO AO CARREGAR
// ============================================================================

window.addEventListener('load', function() {
    setupInputMasks();
    initializeDarkMode();
});
