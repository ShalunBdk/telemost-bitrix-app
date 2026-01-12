// Utility functions for the Telemost-Bitrix application

// Function to show notifications
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification notification-${type} fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 max-w-sm`;
  
  // Set background color based on type
  switch(type) {
    case 'success':
      notification.style.backgroundColor = '#48bb78';
      break;
    case 'error':
      notification.style.backgroundColor = '#f56565';
      break;
    case 'warning':
      notification.style.backgroundColor = '#ed8936';
      break;
    default:
      notification.style.backgroundColor = '#3182ce';
  }
  
  notification.style.color = 'white';
  notification.textContent = message;
  
  // Add to page
  document.body.appendChild(notification);
  
  // Remove after 5 seconds
  setTimeout(() => {
    notification.remove();
  }, 5000);
}

// Function to copy text to clipboard
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showNotification('Ссылка скопирована в буфер обмена', 'success');
    return true;
  } catch (err) {
    console.error('Failed to copy text: ', err);
    showNotification('Не удалось скопировать ссылку', 'error');
    return false;
  }
}

// Function to format dates
function formatDate(dateString) {
  const options = { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
  return new Date(dateString).toLocaleDateString('ru-RU', options);
}

// Function to handle API calls with error handling
async function apiCall(endpoint, method = 'GET', data = null) {
  const options = {
    method: method,
    headers: {
      'Content-Type': 'application/json',
    }
  };
  
  if (data) {
    options.body = JSON.stringify(data);
  }
  
  try {
    const response = await fetch(endpoint, options);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API call error:', error);
    showNotification(`Ошибка: ${error.message}`, 'error');
    throw error;
  }
}

// Function to validate email
function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

// Function to debounce other functions
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}