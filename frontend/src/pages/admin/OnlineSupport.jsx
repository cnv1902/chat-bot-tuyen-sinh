import React, { useState, useEffect, useRef } from 'react';
import { Search, Send, MoreVertical, Phone, Video, CheckCheck, Clock, User, Bell } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import './OnlineSupport.css';

export default function OnlineSupport() {
  const { showToast } = useOutletContext() || {};
  const [conversations, setConversations] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [inputText, setInputText] = useState("");
  const messagesEndRef = useRef(null);

  const fetchConversations = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/admin/support/conversations");
      const data = await res.json();
      if (data.success) {
        const formatted = data.data.map(c => ({
          id: c.session_id,
          candidateName: c.candidate_name || "Thí sinh Khách",
          avatar: `https://ui-avatars.com/api/?name=Khách&background=random`,
          lastMessage: c.last_message || "Yêu cầu kết nối",
          time: "Vừa xong",
          unread: 0,
          status: "waiting",
          major: c.major || "Chưa rõ",
          phone: "Chưa có",
          email: "Chưa có",
          history: c.history || []
        }));
        setConversations(formatted);
      }
    } catch (err) {
      console.error("Lỗi lấy danh sách", err);
    }
  };

  useEffect(() => {
    fetchConversations();
    
    // Kết nối tới SSE Handoff Backend
    const eventSource = new EventSource("http://localhost:8000/api/admin/support/stream");
    
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === "handoff_request") {
          const data = payload.data;
          // Phát âm thanh cảnh báo (tuỳ chọn)
          if (showToast) {
            showToast(`Yêu cầu Handoff mới: ${data.major}`, "success");
          }
          
          // Tạo đoạn chat mới nếu chưa có
          setConversations(prev => {
            const exists = prev.find(c => c.id === data.session_id);
            if (exists) return prev;
            
            const newChat = {
              id: data.session_id, // Sử dụng session_id thật
              candidateName: data.candidate_name || "Thí sinh Khách",
              avatar: "https://ui-avatars.com/api/?name=Khách&background=random",
              lastMessage: data.last_message || "Yêu cầu kết nối",
              time: "Vừa xong",
              unread: 1,
              status: "waiting",
              major: data.major || "Chưa rõ",
              phone: "Chưa có",
              email: "Chưa có",
              history: data.history || []
            };
            return [newChat, ...prev];
          });
        } else if (payload.event === "new_message") {
          const { session_id, message } = payload.data;
          setConversations(prev => prev.map(c => {
            if (c.id === session_id) {
              return {
                ...c,
                history: [...c.history, message],
                lastMessage: message.text,
                unread: activeChatId === session_id ? 0 : c.unread + 1
              };
            }
            return c;
          }));
        } else if (payload.event === "handoff_ended") {
          const { session_id } = payload.data;
          setConversations(prev => prev.filter(c => c.id !== session_id));
          if (activeChatId === session_id) setActiveChatId(null);
          if (showToast) showToast("Thí sinh đã kết thúc cuộc trò chuyện", "info");
        }
      } catch (err) {
        console.error("Lỗi parse event SSE", err);
      }
    };
    
    eventSource.onerror = (err) => {
      console.error("SSE Handoff lỗi kết nối:", err);
    };

    return () => {
      eventSource.close();
    };
  }, [showToast, activeChatId]);

  const activeChat = conversations.find(c => c.id === activeChatId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.history]);

  const handleSendMessage = async () => {
    if (!inputText.trim() || !activeChatId) return;

    try {
      const res = await fetch("http://localhost:8000/api/admin/support/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeChatId, message: inputText })
      });
      const data = await res.json();
      if (data.success) {
        setInputText("");
        // Cập nhật UI ngay lập tức
        setConversations(prev => prev.map(c => {
          if (c.id === activeChatId) {
            return {
              ...c,
              history: [...c.history, data.data],
              lastMessage: data.data.text
            };
          }
          return c;
        }));
      }
    } catch (err) {
      console.error("Lỗi gửi tin nhắn", err);
    }
  };

  const handleEndHandoff = async () => {
    if (!activeChatId) return;
    try {
      const res = await fetch("http://localhost:8000/api/admin/support/end-handoff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeChatId })
      });
      const data = await res.json();
      if (data.success) {
        setConversations(prev => prev.filter(c => c.id !== activeChatId));
        setActiveChatId(null);
        if (showToast) showToast("Đã kết thúc hỗ trợ.", "success");
      }
    } catch (err) {
      console.error("Lỗi kết thúc", err);
    }
  };

  return (
    <div className="zalo-container">
      {/* CỘT 1: DANH SÁCH CHAT (LEFT SIDEBAR) */}
      <div className="zalo-sidebar">
        <div className="zalo-sidebar-header">
          <h2>Hỗ trợ trực tuyến</h2>
          <div className="zalo-search-box">
            <Search size={16} className="search-icon" />
            <input type="text" placeholder="Tìm kiếm thí sinh..." />
          </div>
          <div className="zalo-tabs">
            <button className="zalo-tab active">Tất cả</button>
            <button className="zalo-tab">Đang chờ <span className="badge">2</span></button>
          </div>
        </div>

        <div className="zalo-chat-list">
          {conversations.map(chat => (
            <div 
              key={chat.id}  
              className={`zalo-chat-item ${activeChatId === chat.id ? 'active' : ''}`}
              onClick={() => setActiveChatId(chat.id)}
            >
              <div className="avatar-wrapper">
                <img src={chat.avatar} alt="avatar" />
                <div className={`status-dot ${chat.status === 'active' ? 'online' : 'busy'}`}></div>
              </div>
              <div className="chat-preview">
                <div className="chat-preview-header">
                  <h4>{chat.candidateName}</h4>
                  <span className="time">{chat.time}</span>
                </div>
                <div className="chat-preview-content">
                  <p className={chat.unread > 0 ? "unread-text" : ""}>{chat.lastMessage}</p>
                  {chat.unread > 0 && <span className="unread-badge">{chat.unread}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CỘT 2: KHUNG CHAT (MAIN CHAT AREA) */}
      <div className="zalo-main">
        {activeChat ? (
          <>
            <div className="zalo-main-header">
              <div className="chat-user-info">
                <img src={activeChat.avatar} alt="avatar" />
                <div>
                  <h3>{activeChat.candidateName}</h3>
                  <span>{activeChat.status === 'active' ? 'Đang trực tuyến' : 'Đang chờ hỗ trợ'}</span>
                </div>
              </div>
              <div className="chat-actions">
                <button><Phone size={20} /></button>
                <button><Video size={20} /></button>
                <button><MoreVertical size={20} /></button>
              </div>
            </div>

            <div className="zalo-message-area">
              <div className="chat-date-divider"><span>Hôm nay</span></div>
              {activeChat.history.map(msg => (
                <div key={msg.id} className={`message-wrapper ${msg.sender === 'staff' ? 'me' : 'them'}`}>
                  {msg.sender === 'candidate' && <img src={activeChat.avatar} className="msg-avatar" alt="avatar" />}
                  <div className="message-content">
                    <div className="message-bubble">
                      <p>{msg.text}</p>
                    </div>
                    <span className="message-time">
                      {msg.time} {msg.sender === 'staff' && <CheckCheck size={12} className="read-receipt" />}
                    </span>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="zalo-input-area">
              <div className="input-box">
                <input 
                  type="text" 
                  placeholder={`Nhắn tin cho ${activeChat.candidateName}...`} 
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                />
                <button 
                  className={`send-btn ${inputText.trim() ? 'active' : ''}`}
                  onClick={handleSendMessage}
                >
                  <Send size={20} />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="zalo-empty-state">
            <div className="empty-icon-wrapper">
              <img src="/dhv_logo.png" alt="Logo" style={{width: 80, opacity: 0.5}} />
            </div>
            <h3>Chào mừng đến với Hỗ trợ trực tuyến</h3>
            <p>Chọn một cuộc trò chuyện từ danh sách bên trái để bắt đầu hỗ trợ thí sinh.</p>
          </div>
        )}
      </div>

      {/* CỘT 3: THÔNG TIN CHI TIẾT (RIGHT PANEL) */}
      {activeChat && (
        <div className="zalo-info-panel">
          <div className="info-header">
            <h3>Thông tin Thí sinh</h3>
          </div>
          <div className="info-profile">
            <img src={activeChat.avatar} alt="avatar" className="info-avatar" />
            <h2>{activeChat.candidateName}</h2>
            <div className="tags">
              <span className="tag primary">{activeChat.major}</span>
            </div>
          </div>
          
          <div className="info-sections">
            <div className="info-section">
              <h4>Chi tiết liên hệ</h4>
              <div className="info-row">
                <Phone size={16} />
                <span>{activeChat.phone}</span>
              </div>
              <div className="info-row">
                <User size={16} />
                <span>{activeChat.email}</span>
              </div>
            </div>

            <div className="info-section">
              <h4>Lịch sử truy vấn AI</h4>
              <div className="ai-history-item">
                <Clock size={14} />
                <p>Hỏi về học phí ngành CNTT (10:15)</p>
              </div>
              <div className="ai-history-item">
                <Clock size={14} />
                <p>Xem điểm chuẩn năm 2025 (10:10)</p>
              </div>
            </div>

            <div className="action-buttons">
              <button className="btn-primary" onClick={handleEndHandoff}>Kết thúc hỗ trợ</button>
              <button className="btn-secondary">Chuyển tiếp cho cán bộ khác</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
