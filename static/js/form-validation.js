// static/js/form-validation.js

document.addEventListener('DOMContentLoaded', function() {
    // Get form elements
    const usernameField = document.getElementById('id_username');
    const emailField = document.getElementById('id_email');
    const mobileField = document.getElementById('id_mobile_number');
    const passwordField = document.getElementById('id_password1');
    const confirmPasswordField = document.getElementById('id_password2');
    
    const COMMON_PASSWORDS = [
        '123456', 'password', '12345678', 'qwerty', '123456789', 
        '12345', '1234', '111111', '1234567', 'dragon', 
        '123123', 'baseball', 'abc123', 'football', 'monkey', 
        'letmein', '696969', 'shadow', 'master', '666666', 
        'qwertyuiop', '123321', 'mustang', '1234567890', 'michael', 
        '654321', 'superman', '1qaz2wsx', '7777777', 
        'batman', 'trustno1', 'welcome', 'admin', 'access',
        'passw0rd', 'p@ssw0rd', 'password1', 'Password', 'Password1',
        'asdfgh', 'asdfghjkl', 'zxcvbnm', 'sunshine', 'iloveyou'
    ];
    
    // Debounce utility function
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }
    
    // Add event listeners for real-time validation with debounce
    if (usernameField) {
        usernameField.addEventListener('input', function() {
            removeValidationFeedback(usernameField);
        });
        usernameField.addEventListener('input', debounce(validateUsername, 500));
    }
    
    if (emailField) {
        emailField.addEventListener('input', function() {
            removeValidationFeedback(emailField);
        });
        emailField.addEventListener('input', debounce(validateEmail, 500));
    }
    
    if (mobileField) {
        mobileField.addEventListener('input', function() {
            removeValidationFeedback(mobileField);
        });
        mobileField.addEventListener('input', debounce(validateMobile, 500));
    }
    
    if (passwordField) {
        passwordField.addEventListener('input', validatePasswordStrength);
    }
    
    if (confirmPasswordField && passwordField) {
        confirmPasswordField.addEventListener('input', function() {
            validatePasswordMatch(passwordField, confirmPasswordField);
        });
    }
    
    // Form submission validation
    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', function(e) {
            let isValid = true;
            
            // Validate all fields
            if (usernameField && usernameField.value.trim()) {
                if (usernameField.classList.contains('is-invalid')) {
                    isValid = false;
                }
            }
            
            if (emailField && emailField.value.trim()) {
                if (emailField.classList.contains('is-invalid')) {
                    isValid = false;
                }
            }
            
            if (mobileField && mobileField.value.trim()) {
                if (mobileField.classList.contains('is-invalid')) {
                    isValid = false;
                }
            }
            
            // Check if password field exists and has a value
            if (passwordField && passwordField.value) {
                // Get user info for similarity check
                const userInfo = {
                    username: usernameField ? usernameField.value : '',
                    email: emailField ? emailField.value : '',
                    firstName: document.getElementById('id_first_name') ? document.getElementById('id_first_name').value : '',
                    lastName: document.getElementById('id_last_name') ? document.getElementById('id_last_name').value : ''
                };
                
                // Run password validation
                const passwordRules = validatePasswordRules(passwordField.value, userInfo);
                const allRulesPassed = passwordRules.every(rule => rule.passed);
                
                // Check if passwords match
                const passwordsMatch = !confirmPasswordField || 
                                    (confirmPasswordField.value === passwordField.value);
                
                if (!allRulesPassed || !passwordsMatch) {
                    isValid = false;
                }
            }
            
            if (!isValid) {
                e.preventDefault(); // Prevent form submission
                
                // Find the first invalid field and scroll to it
                const firstInvalid = signupForm.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }
            }
        });
    }
    
    // Validation functions
    function validateUsername() {
        const username = usernameField.value.trim();
        
        if (username.length < 3) {
            showValidationFeedback(usernameField, 'Username must be at least 3 characters long', false);
            return;
        }
        
        // AJAX call to check username availability
        fetch('/accounts/check-username/?username=' + encodeURIComponent(username))
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.is_taken) {
                    showValidationFeedback(usernameField, 'This username is already taken', false);
                } else {
                    showValidationFeedback(usernameField, 'Username is available', true);
                }
            })
            .catch(error => {
                console.error('Error checking username:', error);
                showValidationFeedback(usernameField, 'Unable to verify username. Please try again.', false);
            });
    }
    
    function validateEmail() {
        const email = emailField.value.trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        
        if (!emailRegex.test(email)) {
            showValidationFeedback(emailField, 'Please enter a valid email address', false);
            return;
        }
        
        // AJAX call to check email availability
        fetch('/accounts/check-email/?email=' + encodeURIComponent(email))
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.is_registered) {
                    showValidationFeedback(emailField, 'This email is already registered', false);
                } else {
                    showValidationFeedback(emailField, 'Email is available', true);
                }
            })
            .catch(error => {
                console.error('Error checking email:', error);
                showValidationFeedback(emailField, 'Unable to verify email. Please try again.', false);
            });
    }
    
    function validateMobile() {
        const mobile = mobileField.value.trim();
        // More comprehensive mobile validation regex
        const mobileRegex = /^\+?[0-9]{10,15}$/;
        
        if (!mobileRegex.test(mobile)) {
            showValidationFeedback(mobileField, 'Please enter a valid mobile number (10 digits)', false);
            return;
        }
        
        // AJAX call to check mobile availability
        fetch('/accounts/check-mobile/?mobile=' + encodeURIComponent(mobile))
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.is_registered) {
                    showValidationFeedback(mobileField, 'This mobile number is already registered', false);
                } else {
                    showValidationFeedback(mobileField, 'Mobile number is available', true);
                }
            })
            .catch(error => {
                console.error('Error checking mobile:', error);
                showValidationFeedback(mobileField, 'Unable to verify mobile number. Please try again.', false);
            });
    }
    
    function validatePasswordRules(password, userInfo = {}) {
        const validations = [
            {
                test: () => password.length >= 8,
                message: 'Your password must contain at least 8 characters.',
                passed: false
            },
            {
                test: () => !/^\d+$/.test(password),
                message: 'Your password can\'t be entirely numeric.',
                passed: false
            },
            {
                test: () => {
                    // Check similarity with personal info
                    const personalInfo = [
                        userInfo.username || '',
                        userInfo.email ? userInfo.email.split('@')[0] : '',
                        userInfo.firstName || '',
                        userInfo.lastName || ''
                    ];
                    
                    // Simple similarity check - if password contains or is contained by personal info
                    let tooSimilar = false;
                    for (const info of personalInfo) {
                        if (info.length > 3) {
                            if (password.toLowerCase().includes(info.toLowerCase()) || 
                                info.toLowerCase().includes(password.toLowerCase())) {
                                tooSimilar = true;
                                break;
                            }
                        }
                    }
                    return !tooSimilar;
                },
                message: 'Your password can\'t be too similar to your other personal information.',
                passed: false
            },
            {
                test: () => {
                    return !COMMON_PASSWORDS.includes(password.toLowerCase());
                },
                message: 'Your password can\'t be a commonly used password.',
                passed: false
            }
        ];

        // Run all validations
        for (let validation of validations) {
            validation.passed = validation.test();
        }

        return validations;
    }
    
    function validatePasswordStrength() {
        const password = passwordField.value;
        let strength = 0;
        
        // Remove existing feedback
        removeValidationFeedback(passwordField);
        
        // Get username, email for similarity check
        const userInfo = {
            username: usernameField ? usernameField.value : '',
            email: emailField ? emailField.value : '',
            firstName: document.getElementById('id_first_name') ? document.getElementById('id_first_name').value : '',
            lastName: document.getElementById('id_last_name') ? document.getElementById('id_last_name').value : ''
        };
        
        // Run the specific password rules validation
        const passwordRules = validatePasswordRules(password, userInfo);
        
        // Check if all specific rules are passed
        const allRulesPassed = passwordRules.every(rule => rule.passed);
        
        // Only calculate strength if basic rules pass
        if (allRulesPassed) {
            // Check password length (beyond minimum)
            if (password.length >= 10) {
                strength += 1;
            }
            
            // Check for mixed case
            if (password.match(/[a-z]/) && password.match(/[A-Z]/)) {
                strength += 1;
            }
            
            // Check for numbers
            if (password.match(/\d/)) {
                strength += 1;
            }
            
            // Check for special characters
            if (password.match(/[^a-zA-Z\d]/)) {
                strength += 1;
            }
        }
        
        // Create or update the requirements list
        let requirementsList = document.getElementById('password-requirements');
        
        // Handle requirements list display
        if (password.length === 0) {
            // Remove requirements list when password is empty
            if (requirementsList) {
                requirementsList.remove();
            }
        } else {
            // Create the list if it doesn't exist
            if (!requirementsList) {
                requirementsList = document.createElement('div');
                requirementsList.id = 'password-requirements';
                requirementsList.className = 'mt-2 small';
                passwordField.parentNode.appendChild(requirementsList);
            } else {
                requirementsList.innerHTML = '';
            }
            
            // Add specific requirements with checkmarks or X marks
            const requirementsTitle = document.createElement('div');
            requirementsTitle.textContent = 'Password requirements:';
            requirementsTitle.className = 'fw-bold mb-1';
            requirementsList.appendChild(requirementsTitle);
            
            const reqList = document.createElement('ul');
            reqList.className = 'list-unstyled ms-1';
            
            // Add each validation result to the list
            passwordRules.forEach(rule => {
                const item = document.createElement('li');
                const icon = document.createElement('span');
                icon.className = rule.passed ? 'text-success me-2' : 'text-danger me-2';
                icon.innerHTML = rule.passed ? '✓' : '✗';
                
                item.appendChild(icon);
                item.appendChild(document.createTextNode(rule.message));
                item.className = rule.passed ? 'text-success' : 'text-danger';
                
                reqList.appendChild(item);
            });
            
            requirementsList.appendChild(reqList);
        }
        
        // Handle strength meter display
        let strengthMeter = document.getElementById('password-strength-meter');
        
        if (password.length === 0) {
            // Remove the meter when password is empty
            if (strengthMeter) {
                strengthMeter.remove();
            }
        } else {
            // Create meter if it doesn't exist
            if (!strengthMeter) {
                strengthMeter = document.createElement('div');
                strengthMeter.id = 'password-strength-meter';
                strengthMeter.className = 'mt-2';
                
                const meterBar = document.createElement('div');
                meterBar.className = 'progress';
                meterBar.style.height = '5px';
                
                const meterFill = document.createElement('div');
                meterFill.id = 'password-meter-fill';
                meterFill.className = 'progress-bar';
                meterFill.style.height = '100%';
                meterFill.setAttribute('role', 'progressbar');
                
                const meterText = document.createElement('small');
                meterText.id = 'password-strength-text';
                meterText.className = 'form-text mt-1';
                
                meterBar.appendChild(meterFill);
                strengthMeter.appendChild(meterBar);
                strengthMeter.appendChild(meterText);
                
                passwordField.parentNode.appendChild(strengthMeter);
            }
            
            // Update meter
            const meterFill = document.getElementById('password-meter-fill');
            const meterText = document.getElementById('password-strength-text');
            
            // Update based on rules and strength
            if (!allRulesPassed) {
                // If any rule fails, show red meter
                meterFill.style.width = '25%';
                meterFill.className = 'progress-bar bg-danger';
                meterText.textContent = 'Password doesn\'t meet requirements';
                meterText.className = 'form-text text-danger mt-1';
                
                // Add is-invalid class to the input
                passwordField.classList.add('is-invalid');
            } else {
                // Calculate percentage based on strength
                const percentage = (strength / 4) * 100;
                meterFill.style.width = percentage + '%';
                
                // Update meter color and text based on strength
                if (strength < 2) {
                    meterFill.className = 'progress-bar bg-warning';
                    meterText.textContent = 'Weak password';
                    meterText.className = 'form-text text-warning mt-1';
                } else if (strength < 3) {
                    meterFill.className = 'progress-bar bg-info';
                    meterText.textContent = 'Moderate password';
                    meterText.className = 'form-text text-info mt-1';
                } else if (strength < 4) {
                    meterFill.className = 'progress-bar bg-primary';
                    meterText.textContent = 'Good password';
                    meterText.className = 'form-text text-primary mt-1';
                } else {
                    meterFill.className = 'progress-bar bg-success';
                    meterText.textContent = 'Strong password';
                    meterText.className = 'form-text text-success mt-1';
                }
                
                // Remove invalid class since rules passed
                passwordField.classList.remove('is-invalid');
            }
        }
        
        // Update confirm password validation if exists and has value
        if (confirmPasswordField && confirmPasswordField.value) {
            validatePasswordMatch(passwordField, confirmPasswordField);
        }
        
        // Return validation status
        return allRulesPassed;
    }
    
    function validatePasswordMatch(passwordField, confirmField) {
        const password = passwordField.value;
        const confirmPassword = confirmField.value;
        
        // Remove existing validation feedback first
        removeValidationFeedback(confirmField);
        
        if (confirmPassword.length === 0) {
            return;
        }
        
        if (password === confirmPassword) {
            showValidationFeedback(confirmField, 'Passwords match', true);
        } else {
            showValidationFeedback(confirmField, 'Passwords do not match', false);
        }
    }
    
    // Helper functions for displaying validation feedback
    function showValidationFeedback(inputField, message, isValid) {
        // Remove any existing feedback
        removeValidationFeedback(inputField);
        
        // Add the appropriate class to the input
        if (isValid) {
            inputField.classList.add('is-valid');
        } else {
            inputField.classList.add('is-invalid');
        }
        
        // Create feedback element
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = isValid ? 'valid-feedback' : 'invalid-feedback';
        feedbackDiv.textContent = message;
        
        // Add icon to feedback
        const iconSpan = document.createElement('span');
        iconSpan.className = isValid ? 'text-success me-1' : 'text-danger me-1';
        iconSpan.innerHTML = isValid ? '✓' : '✗';
        
        feedbackDiv.prepend(iconSpan);
        
        // Add feedback after the input
        inputField.parentNode.appendChild(feedbackDiv);
        
        // Make sure feedback is visible
        feedbackDiv.style.display = 'block';
    }
    
    function removeValidationFeedback(inputField) {
        // Remove validation classes
        inputField.classList.remove('is-valid', 'is-invalid');
        
        // Remove feedback elements
        const feedback = inputField.parentNode.querySelectorAll('.valid-feedback, .invalid-feedback');
        feedback.forEach(element => {
            element.remove();
        });
    }
});