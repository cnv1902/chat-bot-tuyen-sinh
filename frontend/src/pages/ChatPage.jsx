import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  Sparkles,
  Settings,
  MessageSquare,
  ChevronRight,
  Info,
  HelpCircle,
  ArrowRight,
  LogIn,
  User,
  LogOut
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SUGGESTED_QUESTIONS = [
  'Điểm chuẩn ngành Công nghệ thông tin năm 2026 là bao nhiêu?',
  'Học phí ngành Sư phạm Toán học năm nay thế nào?',
  'Trường có những chương trình học bổng nào cho tân sinh viên?',
  'Chỉ tiêu tuyển sinh ngành Luật kinh tế năm 2026 là bao nhiêu?',
  'Quy chế xét tuyển thẳng của Đại học Vinh gồm những gì?'
];

export default function ChatPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('chat_messages');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error("Error parsing chat_messages:", e);
      }
    }
    return [
      {
        role: 'assistant',
        content: 'Xin chào! Tôi là Trợ lý ảo tư vấn tuyển sinh chính thức của **Trường Đại học Vinh** 🏛️\n\nTôi có thể giải đáp các thông tin về:\n* 📊 **Điểm chuẩn** các năm\n* 💰 **Học phí & Học bổng**\n* 📋 **Chỉ tiêu tuyển sinh**\n* 📜 **Quy chế & Thủ tục** xét tuyển thẳng\n\nBạn cần tôi hỗ trợ thông tin gì hôm nay?'
      }
    ];
  });
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    const savedId = localStorage.getItem('chat_session_id');
    if (savedId) return savedId;
    const newId = crypto.randomUUID();
    localStorage.setItem('chat_session_id', newId);
    return newId;
  });
  const [userInfo, setUserInfo] = useState(() => {
    const saved = localStorage.getItem('user_info');
    return saved ? JSON.parse(saved) : null;
  });
  const [showUserModal, setShowUserModal] = useState(false);

  // Lưu messages vào LocalStorage mỗi khi có thay đổi
  useEffect(() => {
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages]);

  const handleGoogleLogin = () => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    if (!clientId) {
      alert("Chưa cấu hình VITE_GOOGLE_CLIENT_ID");
      return;
    }
    const redirectUri = `${window.location.origin}/auth/google/callback`;
    const scope = "email profile";
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scope)}`;
    window.location.href = authUrl;
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    setUserInfo(null);
    setShowUserModal(false);
  };

  const handleResetChat = () => {
    setShowResetModal(true);
  };

  const confirmResetChat = () => {
    const newId = crypto.randomUUID();
    localStorage.setItem('chat_session_id', newId);
    setSessionId(newId);
    const initialMessages = [
      {
        role: 'assistant',
        content: 'Xin chào! Tôi là Trợ lý ảo tư vấn tuyển sinh chính thức của **Trường Đại học Vinh** 🏛️\n\nTôi có thể giải đáp các thông tin về:\n* 📊 **Điểm chuẩn** các năm\n* 💰 **Học phí & Học bổng**\n* 📋 **Chỉ tiêu tuyển sinh**\n* 📜 **Quy chế & Thủ tục** xét tuyển thẳng\n\nBạn cần tôi hỗ trợ thông tin gì hôm nay?'
      }
    ];
    setMessages(initialMessages);
    localStorage.setItem('chat_messages', JSON.stringify(initialMessages));
    setShowResetModal(false);
  };

  const endOfMessagesRef = useRef(null);

  const scrollToBottom = () => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend) => {
    if (!textToSend.trim() || isLoading) return;

    const userMessage = textToSend.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: userMessage }),
      });
      const data = await response.json();

      if (response.ok) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.answer,
          sources: data.sources
        }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Hệ thống đang bận hoặc gặp sự cố xử lý. Vui lòng thử lại sau giây lát.'
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Không thể kết nối đến máy chủ API tuyển sinh.'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    const text = input;
    setInput('');
    handleSendMessage(text);
  };

  return (
    <div className="chat-layout">

      {/* PANEL GIỚI THIỆU BÊN TRÁI (ẨN TRÊN MOBILE) */}
      <aside className="chat-panel-left">
        <div className="school-info-card">
          <div className="school-logo-container" style={{ backgroundColor: 'transparent', border: 'none', padding: '0' }}>
            <img src="/dhv_logo.png" alt="Đại học Vinh Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
          <h2 style={{ fontSize: '1.2rem', color: '#ffffff', margin: 0, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Đại học Vinh
          </h2>
          <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)', marginTop: '4px', letterSpacing: '1px' }}>
            THÔNG TIN TUYỂN SINH
          </span>
        </div>

        <div className="faq-list">
          <div className="faq-title">
            <HelpCircle size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
            Câu hỏi gợi ý
          </div>

          {SUGGESTED_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              className="faq-item"
              onClick={() => handleSendMessage(q)}
              disabled={isLoading}
            >
              {q}
            </button>
          ))}
        </div>

        {/* Nút vào admin ở bottom sidebar trái */}
        <div style={{ padding: '20px', borderTop: '1.5px solid var(--border-color)', backgroundColor: '#f8fafc' }}>
          <button
            onClick={() => navigate('/admin')}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '12px 20px',
              backgroundColor: 'var(--text-main)',
              color: '#ffffff',
              fontWeight: 'bold',
              fontSize: '0.88rem'
            }}
            onMouseOver={e => e.currentTarget.style.backgroundColor = 'var(--primary-blue)'}
            onMouseOut={e => e.currentTarget.style.backgroundColor = 'var(--text-main)'}
          >
            <Settings size={16} />
            TRANG QUẢN TRỊ HỆ THỐNG
          </button>
        </div>
      </aside>

      {/* CỬA SỔ CHAT CHÍNH BÊN PHẢI */}
      <main className="chat-panel-right">
        {/* HEADER CHAT */}
        <header style={{
          height: 'var(--header-height)',
          backgroundColor: 'var(--primary-blue)',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          color: '#ffffff',
          zIndex: 5
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div>
              <h1 style={{ fontSize: '1.05rem', color: '#ffffff', margin: 0, fontWeight: 'bold' }}>Trợ lý Tuyển sinh ĐH Vinh</h1>
              <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.8)' }}>Hỗ trợ thông tin 24/7</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', position: 'relative' }}>
            <button
              onClick={handleResetChat}
              style={{
                backgroundColor: 'transparent',
                color: '#ffffff',
                border: '1px solid rgba(255,255,255,0.4)',
                padding: '8px 14px',
                fontSize: '0.8rem',
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
                borderRadius: '20px'
              }}
              onMouseOver={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
              onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <Sparkles size={14} />
              <span className="hide-on-mobile">Hội thoại mới</span>
            </button>

            {userInfo ? (
              <button
                onClick={() => setShowUserModal(!showUserModal)}
                style={{
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  color: '#ffffff',
                  border: '1px solid rgba(255,255,255,0.4)',
                  padding: '8px 14px',
                  fontSize: '0.8rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  borderRadius: '20px'
                }}
              >
                <User size={14} />
                <span>{userInfo.full_name || userInfo.username?.split('@')[0]}</span>
              </button>
            ) : (
              <button
                onClick={handleGoogleLogin}
                style={{
                  backgroundColor: '#ffffff',
                  color: '#333333',
                  border: '1px solid #dcdcdc',
                  padding: '8px 14px',
                  fontSize: '0.8rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  borderRadius: '20px'
                }}
              >
                <LogIn size={14} color="#db4437" />
                <span className="hide-on-mobile">Đăng nhập Google</span>
              </button>
            )}

            {/* Modal Thông tin User */}
            {showUserModal && userInfo && (
              <div style={{
                position: 'absolute',
                top: '100%',
                right: '40px',
                marginTop: '12px',
                backgroundColor: '#ffffff',
                color: '#333333',
                borderRadius: '8px',
                boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
                padding: '16px',
                width: '260px',
                zIndex: 100,
                border: '1px solid #e2e8f0',
                animation: 'slideUp 0.15s ease',
                textAlign: 'left'
              }}>
                <div style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '12px', marginBottom: '12px' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '0.95rem', color: '#1e293b' }}>{userInfo.full_name || 'Hồ sơ Thí sinh'}</div>
                  <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{userInfo.username}</div>
                  <div style={{ fontSize: '0.75rem', marginTop: '6px', display: 'inline-block', padding: '2px 8px', backgroundColor: '#e0f2fe', color: '#0369a1', borderRadius: '4px', fontWeight: 'bold' }}>
                    Role: {userInfo.role}
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '8px 12px',
                    backgroundColor: '#fee2e2',
                    color: '#dc2626',
                    border: 'none',
                    borderRadius: '6px',
                    fontWeight: 'bold',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    transition: 'background-color 0.15s'
                  }}
                  onMouseOver={e => e.currentTarget.style.backgroundColor = '#fecaca'}
                  onMouseOut={e => e.currentTarget.style.backgroundColor = '#fee2e2'}
                >
                  <LogOut size={14} />
                  Đăng xuất
                </button>
              </div>
            )}

            {/* Nút Admin hiển thị trên Mobile */}
            <div className="mobile-admin-btn">
              <button
                onClick={() => navigate('/admin')}
                style={{
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  color: '#ffffff',
                  border: '1px solid rgba(255,255,255,0.4)',
                  padding: '8px 14px',
                  fontSize: '0.8rem',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  borderRadius: '20px'
                }}
              >
                <Settings size={14} />
                <span className="hide-on-mobile">Quản trị</span>
              </button>
            </div>
          </div>
          <style>{`
            .mobile-admin-btn { display: none; }
            @media (max-width: 992px) {
              .mobile-admin-btn { display: block !important; }
              .hide-on-mobile { display: none; }
            }
          `}</style>
        </header>

        {/* CONTAINER TIN NHẮN CHAT */}
        <div style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '32px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
        }}>
          <div style={{ maxWidth: '900px', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>

            {messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={idx}
                  style={{
                    alignSelf: isUser ? 'flex-end' : 'flex-start',
                    maxWidth: '85%',
                    display: 'flex',
                    gap: '16px',
                    flexDirection: isUser ? 'row-reverse' : 'row'
                  }}
                >
                  {/* Bot Avatar */}
                  {!isUser && (
                    <div style={{
                      width: '36px',
                      height: '36px',
                      minWidth: '36px',
                      marginTop: '4px'
                    }}>
                      <img src="/dhv_logo.png" alt="AI Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                    </div>
                  )}

                  <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    alignItems: isUser ? 'flex-end' : 'flex-start'
                  }}>
                    {/* Tên người gửi */}
                    {!isUser && (
                      <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-main)' }}>
                        Trợ lý Tuyển sinh AI
                      </span>
                    )}

                    {/* Bong bóng chat */}
                    <div style={{
                      padding: '16px 20px',
                      backgroundColor: isUser ? 'var(--primary-blue)' : 'var(--bg-white)',
                      color: isUser ? '#ffffff' : 'var(--text-main)',
                      border: isUser ? 'none' : '1.5px solid var(--border-color)',
                      boxShadow: isUser ? 'none' : '4px 4px 0px rgba(0, 102, 255, 0.03)',
                      fontSize: '0.96rem',
                      lineHeight: '1.6',
                      width: '100%'
                    }}>
                      {isUser ? (
                        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                      ) : (
                        <div className="markdown-body">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>

                    {/* Sources link (nếu có) */}
                    {!isUser && msg.sources && msg.sources.length > 0 && (
                      <div style={{
                        fontSize: '0.78rem',
                        color: 'var(--text-muted)',
                        marginTop: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        backgroundColor: '#f1f5f9',
                        padding: '4px 10px',
                        border: '1px solid var(--border-color)'
                      }}>
                        <Sparkles size={12} color="var(--primary-blue)" />
                        <span>Nguồn trích dẫn: <b>{msg.sources.join(', ')}</b></span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div style={{ alignSelf: 'flex-start', maxWidth: '85%', display: 'flex', gap: '16px' }}>
                <div style={{
                  width: '36px',
                  height: '36px',
                  minWidth: '36px',
                  marginTop: '4px'
                }}>
                  <img src="/dhv_logo.png" alt="AI Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-main)' }}>Trợ lý Tuyển sinh AI</span>
                  <div style={{
                    padding: '16px 20px',
                    backgroundColor: 'var(--bg-white)',
                    border: '1.5px solid var(--border-color)',
                    color: 'var(--text-muted)',
                    fontStyle: 'italic',
                    fontSize: '0.95rem'
                  }}>
                    Đang phân tích tri thức tuyển sinh và soạn câu trả lời...
                  </div>
                </div>
              </div>
            )}
            <div ref={endOfMessagesRef} />

          </div>
        </div>

        {/* FOOTER NHẬP TIN NHẮN */}
        <footer style={{
          padding: '20px 24px',
          backgroundColor: 'var(--bg-white)',
          borderTop: '1px solid var(--border-color)',
          zIndex: 4
        }}>
          <div style={{ maxWidth: '900px', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>

            {/* Scrollable Câu hỏi gợi ý trượt ngang trên Mobile */}
            <div className="mobile-faq-scroll" style={{
              display: 'none', // Sẽ được bật trên Mobile bằng CSS bên dưới
              gap: '8px',
              overflowX: 'auto',
              paddingBottom: '8px',
              WebkitOverflowScrolling: 'touch'
            }}>
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(q)}
                  disabled={isLoading}
                  style={{
                    padding: '8px 14px',
                    backgroundColor: 'var(--bg-main)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-main)',
                    fontSize: '0.78rem',
                    fontWeight: '500',
                    whiteSpace: 'nowrap',
                    flexShrink: 0
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
            <style>{`
              @media (max-width: 992px) {
                .mobile-faq-scroll { display: flex !important; }
              }
            `}</style>

            {/* Form Input chính */}
            <form onSubmit={handleSubmit} style={{
              display: 'flex',
              border: '1.5px solid var(--border-color)',
              backgroundColor: 'var(--bg-main)',
              transition: 'border-color 0.15s ease'
            }}
              onFocus={e => e.currentTarget.style.borderColor = 'var(--primary-blue)'}
              onBlur={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
            >
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Hỏi trợ lý về điểm chuẩn, học phí, thủ tục tuyển sinh..."
                disabled={isLoading}
                style={{
                  flex: 1,
                  padding: '16px 20px',
                  backgroundColor: 'transparent',
                  color: 'var(--text-main)',
                  fontSize: '0.98rem',
                  border: 'none',
                  outline: 'none'
                }}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                style={{
                  padding: '0 24px',
                  backgroundColor: 'transparent',
                  color: (isLoading || !input.trim()) ? 'var(--text-muted)' : 'var(--primary-blue)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Send size={20} />
              </button>
            </form>
          </div>
        </footer>

      </main>

      {/* MODAL XÁC NHẬN BẮT ĐẦU MỚI HỘI THOẠI */}
      {showResetModal && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setShowResetModal(false); }}
          style={{
            position: 'fixed', inset: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(3px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 10000,
            animation: 'fadeIn 0.15s ease'
          }}
        >
          <div
            style={{
              backgroundColor: '#ffffff',
              border: '1.5px solid #e2e8f0',
              boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
              padding: '0',
              width: '100%',
              maxWidth: '400px',
              margin: '16px',
              animation: 'slideUp 0.2s ease',
              overflow: 'hidden'
            }}
          >
            <div style={{
              backgroundColor: 'var(--primary-blue)',
              padding: '20px 24px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <div style={{
                width: '36px', height: '36px',
                backgroundColor: 'rgba(255,255,255,0.15)',
                borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0
              }}>
                <Sparkles size={18} color="#ffffff" />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 800, fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Bắt đầu hội thoại mới
                </div>
              </div>
            </div>

            <div style={{ padding: '24px' }}>
              <p style={{ fontSize: '0.9rem', color: '#374151', marginBottom: '24px', lineHeight: '1.6' }}>
                Bạn có chắc chắn muốn xóa lịch sử cuộc trò chuyện hiện tại và bắt đầu một phiên tư vấn mới không?
              </p>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowResetModal(false)}
                  style={{
                    padding: '10px 20px',
                    border: '1.5px solid #e2e8f0',
                    backgroundColor: '#ffffff',
                    color: '#374151',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  onMouseOver={e => { e.currentTarget.style.backgroundColor = '#f8fafc'; }}
                  onMouseOut={e => { e.currentTarget.style.backgroundColor = '#ffffff'; }}
                >
                  HỦY BỎ
                </button>
                <button
                  onClick={confirmResetChat}
                  style={{
                    padding: '10px 20px',
                    border: '1.5px solid var(--primary-blue)',
                    backgroundColor: 'var(--primary-blue)',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  onMouseOver={e => { e.currentTarget.style.backgroundColor = '#2563eb'; e.currentTarget.style.borderColor = '#2563eb'; }}
                  onMouseOut={e => { e.currentTarget.style.backgroundColor = 'var(--primary-blue)'; e.currentTarget.style.borderColor = 'var(--primary-blue)'; }}
                >
                  BẮT ĐẦU MỚI
                </button>
              </div>
            </div>
          </div>
          <style>{`
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            @keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
          `}</style>
        </div>
      )}

    </div>
  );
}
