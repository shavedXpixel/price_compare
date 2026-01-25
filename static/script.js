document.addEventListener("DOMContentLoaded", () => {
    
    // Select the forms and buttons
    const loginBox = document.querySelector('.form-box.login');
    const registerBox = document.querySelector('.form-box.register');
    const registerBtn = document.querySelector('.register-btn');
    const loginBtn = document.querySelector('.login-btn');

    // Show Register Form
    registerBtn.addEventListener('click', (e) => {
        e.preventDefault(); // Stop link from jumping
        loginBox.style.display = 'none';
        registerBox.style.display = 'flex';
    });

    // Show Login Form
    loginBtn.addEventListener('click', (e) => {
        e.preventDefault(); // Stop link from jumping
        registerBox.style.display = 'none';
        loginBox.style.display = 'flex';
    });

});