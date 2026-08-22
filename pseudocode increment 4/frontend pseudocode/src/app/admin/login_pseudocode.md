# Pseudocode: Admin Login Page

## File: `app/admin/login/page.tsx`

```markdown
ALGORITMA ADMIN LOGIN PAGE (admin/login/page.tsx)

1. COMPONENT SETUP
   - 'use client' directive untuk client-side rendering
   - useState hooks untuk form state management
   - useRouter untuk navigation
   - Lucide icons untuk UI (Eye, EyeOff)
   - adminLogin function dari lib/adminAuth

2. STATE MANAGEMENT
   - username: string (form input)
   - password: string (form input)
   - rememberMe: boolean (checkbox state)
   - showPassword: boolean (password visibility toggle)
   - isSubmitting: boolean (form submission state)
   - errorMsg: string (error display)
   - userError: boolean (username validation state)
   - passError: boolean (password validation state)

3. FORM VALIDATION FUNCTION
   - Reset error states
   - Check username tidak kosong: setUserError(!username.trim())
   - Check password tidak kosong: setPassError(!password)
   - Return validation result

4. FORM SUBMIT HANDLER
   - preventDefault untuk avoid page reload
   - Clear previous error messages
   - Run form validation
   - JIKA validation gagal: return early
   - Set isSubmitting = true untuk loading state
   - TAHAP LOGIN:
     - await adminLogin(username, password, rememberMe)
     - JIKA success: router.push('/admin/dashboard')
     - JIKA error: setErrorMsg(result.message), setIsSubmitting(false)

5. UI STRUCTURE
   - CONTAINER: admin-login-screen (full screen layout)
   - LEFT PANEL: admin-login-brand
     - Brand blobs untuk visual decoration
     - STMIK WCD logo dan branding
     - Title: "Admin Dashboard"
     - Subtitle: "Chatbot Asisten Virtual RAG"
     - Description: "Kelola knowledge base, chunk dokumen, dan pantau performa sistem"
   
   - RIGHT PANEL: admin-login-form-wrap
     - LOGIN CARD: admin-login-card
       - Header: "Login Admin"
       - FORM FIELDS:
         - Username field dengan validation styling
         - Password field dengan show/hide toggle
         - Remember me checkbox
         - Error message display
         - Submit button dengan loading state
       - Footer: Copyright notice

6. FORM FIELD COMPONENTS
   - Username Field:
     - Label: "Username"
     - Input type="text" dengan autoComplete="username"
     - Error state styling dan message
     - Real-time error clearing pada onChange
   
   - Password Field:
     - Label: "Password" 
     - Input dengan conditional type (text/password)
     - Toggle button dengan Eye/EyeOff icons
     - Error state styling dan message
     - Real-time error clearing pada onChange

7. STYLING FEATURES
   - Responsive design untuk desktop/mobile
   - Brand color scheme (purple theme)
   - Loading states dengan disabled styling
   - Error states dengan validation feedback
   - Smooth animations dan transitions

8. ACCESSIBILITY FEATURES
   - Proper form labels dan associations
   - ARIA labels untuk toggle buttons
   - Keyboard navigation support
   - Screen reader friendly error messages
```

**Login Security Features:**
- Client-side validation dengan real-time feedback
- Password visibility toggle untuk usability
- Remember me functionality dengan secure storage
- Loading states untuk prevent double submission
- Error handling dengan user-friendly messages