// Content script for Avatar Translator Chrome Extension
console.log('Avatar Translator content script loaded');

// Global variables
let currentTargetLanguage = 'es';
let translationOverlay = null;
let isTranslating = false;
let avatarElement = null;
let avatarAnimation = null;
let currentAudio = null;

// Initialize content script
initializeContentScript();

async function initializeContentScript() {
    try {
        // Load current target language
        await loadSettings();
        
        // Set up message handling
        setupMessageHandling();
        
        // Create floating avatar
        createFloatingAvatar();
        
        console.log('Avatar Translator content script initialized successfully');
    } catch (error) {
        console.error('Content script initialization failed:', error);
    }
}

async function loadSettings() {
    try {
        const response = await chrome.runtime.sendMessage({ action: 'getSettings' });
        
        if (response && response.success && response.settings) {
            currentTargetLanguage = response.settings.targetLanguage || 'es';
            console.log('Loaded target language:', currentTargetLanguage);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        // Use default
        currentTargetLanguage = 'es';
    }
}

function setupMessageHandling() {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        try {
            console.log('Content script received message:', request);
            
            switch (request.action) {
                case 'ping':
                    sendResponse({ success: true, timestamp: Date.now() });
                    break;
                    
                case 'translateAudio':
                    handleTranslateAudio(request);
                    sendResponse({ success: true });
                    break;
                    
                case 'translationResult':
                    handleTranslationResult(request);
                    sendResponse({ success: true });
                    break;
                    
                case 'translationComplete':
                    handleTranslationComplete(request);
                    sendResponse({ success: true });
                    break;
                    
                case 'translationError':
                    handleTranslationError(request);
                    sendResponse({ success: true });
                    break;
                    
                default:
                    sendResponse({ success: false, error: 'Unknown action' });
            }
        } catch (error) {
            console.error('Message handler error:', error);
            sendResponse({ success: false, error: error.message });
        }
    });
}

function createFloatingAvatar() {
    try {
        // Remove existing avatar if any
        if (avatarElement) {
            avatarElement.remove();
        }
        
        // Create avatar container
        avatarElement = document.createElement('div');
        avatarElement.id = 'avatar-translator-avatar';
        avatarElement.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            width: 120px;
            height: 120px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            border-radius: 50%;
            z-index: 10000;
            cursor: move;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            color: white;
            user-select: none;
            transition: all 0.3s ease;
        `;
        
        // Set initial avatar state
        avatarElement.innerHTML = '😊';
        avatarElement.title = 'Avatar Translator - Drag to move, click for info';
        
        // Make avatar draggable
        makeDraggable(avatarElement);
        
        // Add click handler for info
        avatarElement.addEventListener('click', showAvatarInfo);
        
        // Add to page
        document.body.appendChild(avatarElement);
        
        console.log('Floating avatar created');
        
    } catch (error) {
        console.error('Error creating floating avatar:', error);
    }
}

function makeDraggable(element) {
    let isDragging = false;
    let startX, startY, startLeft, startTop;
    
    element.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        startLeft = parseInt(element.style.left) || 20;
        startTop = parseInt(element.style.top) || 20;
        
        element.style.cursor = 'grabbing';
        e.preventDefault();
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;
        
        element.style.left = (startLeft + deltaX) + 'px';
        element.style.top = (startTop + deltaY) + 'px';
    });
    
    document.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            element.style.cursor = 'grab';
            
            // Save position
            const x = parseInt(element.style.left) || 20;
            const y = parseInt(element.style.top) || 20;
            chrome.runtime.sendMessage({
                action: 'updateAvatarPosition',
                x: x,
                y: y
            });
        }
    });
}

function showAvatarInfo() {
    const info = `
        🎙️ Avatar Translator
        
        Status: ${isTranslating ? 'Translating...' : 'Ready'}
        Language: ${getLanguageName(currentTargetLanguage)}
        
        Click extension icon to start audio capture!
    `;
    
    // Create temporary info popup
    const infoPopup = document.createElement('div');
    infoPopup.style.cssText = `
        position: fixed;
        top: ${avatarElement.offsetTop - 80}px;
        right: ${avatarElement.offsetLeft + 140}px;
        background: white;
        border: 1px solid #ccc;
        border-radius: 8px;
        padding: 12px;
        font-size: 12px;
        white-space: pre-line;
        z-index: 10001;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        max-width: 200px;
    `;
    infoPopup.textContent = info;
    
    document.body.appendChild(infoPopup);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (infoPopup.parentNode) {
            infoPopup.remove();
        }
    }, 3000);
}

async function handleTranslateAudio(request) {
    try {
        console.log('Starting audio translation:', request);
        
        // Update target language
        if (request.targetLanguage) {
            currentTargetLanguage = request.targetLanguage;
        }
        
        if (isTranslating) {
            showTranslationOverlay('Audio translation already in progress', 'warning');
            return;
        }
        
        isTranslating = true;
        
        // Update avatar to show translating state
        updateAvatarState('translating');
        
        // Show translation start overlay
        const targetLanguageName = getLanguageName(currentTargetLanguage);
        showTranslationOverlay(`🎧 Starting audio capture...`, 'info');
        
        // Request audio capture from background script
        const response = await chrome.runtime.sendMessage({
            action: 'startAudioCapture',
            targetLanguage: currentTargetLanguage
        });
        
        if (response && response.success) {
            showTranslationOverlay(`🎙️ Audio capture started! Listening for audio...`, 'success');
            
            // Auto-hide success message after 3 seconds
            setTimeout(() => {
                if (translationOverlay && translationOverlay.classList.contains('success')) {
                    hideTranslationOverlay();
                }
            }, 3000);
        } else {
            // If background script can't capture, try content script method
            if (response && response.useContentScript) {
                console.log('Background capture failed, trying content script method...');
                await startContentScriptAudioCapture(currentTargetLanguage);
        } else {
            throw new Error(response?.error || 'Failed to start audio capture');
            }
        }
        
    } catch (error) {
        console.error('Audio translation error:', error);
        showTranslationOverlay(`❌ Error: ${error.message}`, 'error');
        isTranslating = false;
        updateAvatarState('error');
    }
}

async function handleTranslationResult(request) {
    try {
        console.log('Received translation result:', request);
        
        if (request.result && request.result.success) {
            const result = request.result.result;
            
            // Store avatar animation data
            if (request.avatarAnimation) {
                avatarAnimation = request.avatarAnimation;
                startAvatarAnimation(avatarAnimation);
            }
            
            // Display the translation result
            if (result.spanish_text) {
        showTranslationOverlay(
                    `✅ Translation Complete!\n\n` +
                    `🔤 English: "${result.english_text}"\n` +
                    `🇪🇸 Spanish: "${result.spanish_text}"\n\n` +
                    `⏱️ Total time: ${result.timings?.total?.toFixed(1)}s`,
            'success'
        );
            } else {
                showTranslationOverlay('✅ Translation completed successfully!', 'success');
            }
            
            // Auto-hide after 8 seconds for detailed results
            setTimeout(() => {
                if (translationOverlay && translationOverlay.classList.contains('success')) {
                    hideTranslationOverlay();
                }
            }, 8000);
            
        } else {
            throw new Error(request.result?.error || 'Translation failed');
        }
        
    } catch (error) {
        console.error('Translation result handling error:', error);
        showTranslationOverlay(`❌ Translation failed: ${error.message}`, 'error');
        updateAvatarState('error');
    } finally {
        isTranslating = false;
        updateAvatarState('ready');
    }
}

function startAvatarAnimation(animation) {
    try {
        if (!avatarElement || !animation) return;
        
        console.log('Starting avatar animation:', animation);
        
        // Update avatar to speaking state
        updateAvatarState('speaking');
        
        // Start lip-sync animation
        let currentFrameIndex = 0;
        const animationInterval = setInterval(() => {
            if (currentFrameIndex >= animation.frames.length) {
                // Animation complete
                clearInterval(animationInterval);
                updateAvatarState('ready');
                return;
            }
            
            const frame = animation.frames[currentFrameIndex];
            updateAvatarFrame(frame);
            currentFrameIndex++;
        }, 100); // 10 FPS animation
        
        // Store interval for cleanup
        avatarAnimation.interval = animationInterval;
        
    } catch (error) {
        console.error('Error starting avatar animation:', error);
    }
}

function updateAvatarFrame(frame) {
    try {
        if (!avatarElement) return;
        
        // Update mouth openness (simple visual representation)
        const mouthOpenness = frame.mouthOpenness;
        const expression = frame.expression;
        
        // Create mouth shape based on openness
        let mouthEmoji = '😊'; // Default
        
        if (mouthOpenness > 0.7) {
            mouthEmoji = '😮'; // Open mouth
        } else if (mouthOpenness > 0.4) {
            mouthEmoji = '😐'; // Slightly open
        } else {
            mouthEmoji = '😊'; // Closed mouth
        }
        
        // Apply expression
        switch (expression) {
            case 'happy':
                mouthEmoji = mouthEmoji === '😊' ? '😊' : '😃';
                break;
            case 'grateful':
                mouthEmoji = '🙏';
                break;
            case 'polite':
                mouthEmoji = '😊';
                break;
            case 'apologetic':
                mouthEmoji = '😔';
                break;
            case 'friendly':
                mouthEmoji = '😊';
                break;
        }
        
        avatarElement.innerHTML = mouthEmoji;
        
    } catch (error) {
        console.error('Error updating avatar frame:', error);
    }
}

function updateAvatarState(state) {
    try {
        if (!avatarElement) return;
        
        switch (state) {
            case 'ready':
                avatarElement.innerHTML = '😊';
                avatarElement.style.background = 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';
                break;
                
            case 'translating':
                avatarElement.innerHTML = '🎙️';
                avatarElement.style.background = 'linear-gradient(135deg, #ffa726 0%, #ff7043 100%)';
                break;
                
            case 'speaking':
                avatarElement.innerHTML = '🗣️';
                avatarElement.style.background = 'linear-gradient(135deg, #66bb6a 0%, #43a047 100%)';
                break;
                
            case 'error':
                avatarElement.innerHTML = '❌';
                avatarElement.style.background = 'linear-gradient(135deg, #ef5350 0%, #d32f2f 100%)';
                break;
        }
        
        console.log('Avatar state updated to:', state);
        
    } catch (error) {
        console.error('Error updating avatar state:', error);
    }
}

async function handleTranslationComplete(request) {
    try {
        console.log('Translation completed:', request);
        
        if (request.result && request.result.success) {
            const result = request.result;
            
            // Display the translation result
            if (result.spanish_text) {
                showTranslationOverlay(
                    `✅ Translation Complete!\n\n` +
                    `🔤 English: "${result.english_text}"\n` +
                    `🇪🇸 Spanish: "${result.spanish_text}"\n\n` +
                    `⏱️ Total time: ${result.timings?.total?.toFixed(1)}s`,
                    'success'
                );
            } else {
                showTranslationOverlay('✅ Translation completed successfully!', 'success');
            }
            
            // Auto-hide after 8 seconds for detailed results
            setTimeout(() => {
                if (translationOverlay && translationOverlay.classList.contains('success')) {
                    hideTranslationOverlay();
                }
            }, 8000);
            
        } else {
            throw new Error(result?.error || 'Translation failed');
        }
        
    } catch (error) {
        console.error('Translation complete handling error:', error);
        showTranslationOverlay(`❌ Translation failed: ${error.message}`, 'error');
        updateAvatarState('error');
    } finally {
        isTranslating = false;
        updateAvatarState('ready');
    }
}

async function handleTranslationError(request) {
    try {
        console.error('Translation error received:', request);
        
        const errorMessage = request.error || 'Unknown translation error';
        showTranslationOverlay(`❌ Translation Error: ${errorMessage}`, 'error');
        updateAvatarState('error');
        
    } catch (error) {
        console.error('Translation error handling error:', error);
        showTranslationOverlay('❌ Translation error occurred', 'error');
    } finally {
        isTranslating = false;
        updateAvatarState('ready');
    }
}

function playTranslatedAudio(base64Audio) {
    try {
        // Convert base64 to blob
        const audioData = atob(base64Audio);
        const audioArray = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
            audioArray[i] = audioData.charCodeAt(i);
        }
        
        const audioBlob = new Blob([audioArray], { type: 'audio/mp3' });
        const audioUrl = URL.createObjectURL(audioBlob);
        
        // Create and play audio element
        const audio = new Audio(audioUrl);
        audio.play().catch(error => {
            console.error('Error playing translated audio:', error);
        });
        
        // Clean up URL after playing
        audio.addEventListener('ended', () => {
            URL.revokeObjectURL(audioUrl);
        });
        
        // Store current audio for control
        currentAudio = audio;
        
        console.log('Playing translated audio');
        
    } catch (error) {
        console.error('Error playing translated audio:', error);
    }
}

function getLanguageName(code) {
    const languages = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese',
        'ar': 'Arabic',
        'hi': 'Hindi'
    };
    return languages[code] || code;
}

function showTranslationOverlay(message, type = 'info') {
    try {
        hideTranslationOverlay();
        
        translationOverlay = document.createElement('div');
        translationOverlay.id = 'avatar-translator-overlay';
        
        const icon = getStatusIcon(type);
        
        // Handle multi-line messages
        const messageLines = message.split('\n');
        const messageHtml = messageLines.map(line => `<div>${line}</div>`).join('');
        
        translationOverlay.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="flex-shrink: 0;">${icon}</span>
                <div style="flex: 1;">${messageHtml}</div>
            </div>
        `;
        
        translationOverlay.style.cssText = getOverlayStyles(type);
        
        document.body.appendChild(translationOverlay);
        
        // Auto-hide after 5 seconds for non-success messages
        if (type !== 'success') {
            setTimeout(() => {
                hideTranslationOverlay();
            }, 5000);
        }
        
    } catch (error) {
        console.error('Translation overlay error:', error);
    }
}

function getStatusIcon(type) {
    switch (type) {
        case 'error': return '❌';
        case 'success': return '✅';
        case 'warning': return '⚠️';
        default: return '🎙️';
    }
}

function getOverlayStyles(type) {
    const baseStyles = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10001;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        max-width: 350px;
        word-wrap: break-word;
        line-height: 1.4;
    `;
    
    const typeStyles = {
        error: 'background: #fee2e2; color: #dc2626; border: 1px solid #fecaca;',
        success: 'background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;',
        warning: 'background: #fffbeb; color: #d97706; border: 1px solid #fed7aa;',
        info: 'background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd;'
    };
    
    return baseStyles + (typeStyles[type] || typeStyles.info);
}

function hideTranslationOverlay() {
    try {
        if (translationOverlay && translationOverlay.parentNode) {
            translationOverlay.parentNode.removeChild(translationOverlay);
        }
        translationOverlay = null;
    } catch (error) {
        console.error('Hide overlay error:', error);
    }
}

// Clean up function for page unload
function cleanup() {
    try {
        // Stop any ongoing avatar animation
        if (avatarAnimation && avatarAnimation.interval) {
            clearInterval(avatarAnimation.interval);
        }
        
        // Stop any playing audio
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        
        // Remove avatar and overlay
        if (avatarElement) {
            avatarElement.remove();
            avatarElement = null;
        }
        
        if (translationOverlay) {
            translationOverlay.remove();
            translationOverlay = null;
        }
        
        console.log('Avatar Translator content script cleaned up');
        
    } catch (error) {
        console.error('Error during cleanup:', error);
    }
}

// Add cleanup on page unload
window.addEventListener('beforeunload', cleanup);
window.addEventListener('pagehide', cleanup);

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Page is hidden, pause any ongoing activities
        if (currentAudio) {
            currentAudio.pause();
        }
    }
});

console.log('Avatar Translator content script functions loaded');

// Content script audio capture fallback function
async function startContentScriptAudioCapture(targetLanguage) {
    try {
        console.log('Starting content script audio capture with WebSocket streaming...');
        
        // Try to capture audio from the page's audio elements
        const audioElements = document.querySelectorAll('audio, video');
        if (audioElements.length === 0) {
            throw new Error('No audio/video elements found on this page');
        }
        
        console.log(`Found ${audioElements.length} audio/video elements`);
        
        // Use the first audio element for capture
        const audioElement = audioElements[0];
        
        // Check if audio is playing
        if (audioElement.paused) {
            throw new Error('Audio is not playing. Please start playing audio first.');
        }
        
        // Start WebSocket streaming with the audio element
        await startContinuousAudioStreaming(audioElement, targetLanguage);
        
        // Show success message
        showTranslationOverlay(`🎙️ Content script audio capture started with WebSocket streaming!`, 'success');
        
    } catch (error) {
        console.error('Content script audio capture failed:', error);
        showTranslationOverlay(`❌ Content script capture error: ${error.message}`, 'error');
        isTranslating = false;
        updateAvatarState('error');
    }
}

// Function to capture audio data from an audio/video element
async function captureAudioFromElement(audioElement, audioContext) {
    return new Promise((resolve) => {
        try {
            // Create a MediaRecorder to capture the audio stream
            const stream = audioElement.captureStream();
            
            if (!stream) {
                resolve(null);
                return;
            }
            
            const mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            const audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };
            
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                console.log('Audio captured successfully:', audioBlob.size, 'bytes');
                resolve(audioBlob);
            };
            
            // Start recording for 5 seconds to capture enough audio
            mediaRecorder.start();
            
            setTimeout(() => {
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                }
            }, 5000);
            
        } catch (error) {
            console.error('Error capturing audio:', error);
            resolve(null);
        }
    });
}

// Continuous audio streaming for long-form content (meetings, movies, etc.)
async function startContinuousAudioStreaming(audioElement, targetLanguage) {
    try {
        console.log('Starting continuous audio streaming...');
        
        // Show streaming started message
        showTranslationOverlay(`🔄 Starting continuous audio streaming...`, 'info');
        
        // Create MediaRecorder for continuous capture
        const stream = audioElement.captureStream();
        if (!stream) {
            throw new Error('Cannot capture audio stream from this element');
        }
        
        const mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        const audioChunks = [];
        let chunkStartTime = Date.now();
        let chunkCounter = 0;
        
        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
                
                // When we have enough audio for a chunk (5 seconds)
                if (audioChunks.length >= 5) { // Adjust based on your chunk size
                    const chunkBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const chunkDuration = (Date.now() - chunkStartTime) / 1000;
                    
                    console.log(`Streaming audio chunk ${++chunkCounter} (${chunkDuration.toFixed(1)}s)`);
                    
                    // Send chunk to background script for WebSocket streaming
                    const response = await chrome.runtime.sendMessage({
                        action: 'streamAudioChunk',
                        audioBlob: chunkBlob,
                        duration: chunkDuration,
                        chunkId: chunkCounter,
                        targetLanguage: targetLanguage
                    });
                    
                    if (response && response.success) {
                        // Update streaming status
                        showTranslationOverlay(
                            `🔄 Streaming Chunk ${chunkCounter}\n\n` +
                            `⏱️ Duration: ${chunkDuration.toFixed(1)}s\n` +
                            `📊 Total: ${(chunkCounter * 5).toFixed(1)}s\n\n` +
                            `🔄 Processing translation...`,
                            'info'
                        );
                    } else {
                        console.error('Failed to stream audio chunk:', response?.error);
                    }
                    
                    // Reset for next chunk
                    audioChunks.length = 0;
                    chunkStartTime = Date.now();
                }
            }
        };
        
        mediaRecorder.onstop = () => {
            console.log('Continuous audio streaming stopped');
            showTranslationOverlay(`⏹️ Audio streaming stopped`, 'info');
        };
        
        mediaRecorder.onerror = (event) => {
            console.error('MediaRecorder error:', event.error);
            showTranslationOverlay(`❌ Streaming error: ${event.error.message}`, 'error');
        };
        
        // Start recording
        mediaRecorder.start(1000); // Collect data every second
        
        // Show streaming active message
        showTranslationOverlay(
            `🎙️ Continuous Audio Streaming Active!\n\n` +
            `🔤 Target: ${getLanguageName(targetLanguage)}\n` +
            `⏱️ Chunk Size: 5 seconds\n` +
            `🔄 Real-time translation enabled\n\n` +
            `📺 Perfect for meetings, movies, and long videos!`,
            'success'
        );
        
        // Auto-hide success message after 8 seconds
        setTimeout(() => {
            if (translationOverlay && translationOverlay.classList.contains('success')) {
                hideTranslationOverlay();
            }
        }, 8000);
        
        // Store mediaRecorder for cleanup
        window.currentMediaRecorder = mediaRecorder;
        
        // Auto-stop after 3 hours (for very long content)
        setTimeout(() => {
            if (mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                showTranslationOverlay(`⏰ Maximum streaming duration reached (3 hours)`, 'info');
            }
        }, 10800000); // 3 hours
        
    } catch (error) {
        console.error('Continuous audio streaming failed:', error);
        throw error;
    }
}
