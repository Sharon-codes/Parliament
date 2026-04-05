import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, ChevronLeft, Check, Smartphone, Link as LinkIcon, Mail } from 'lucide-react';

const Onboarding = () => {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    role: '',
    interests: '',
    projects: '',
    institutions: '',
    proactive: 'balanced',
    style: 'friendly'
  });

  const nextStep = () => setStep(s => Math.min(6, s + 1));
  const prevStep = () => setStep(s => Math.max(1, s - 1));

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleFinish = async () => {
    // Need to save settings via API here later
    // Navigate to dashboard
    navigate('/dashboard');
  };

  const variants = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 },
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-[#faf9f6]">
      {/* Decorative calm background blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-[#e0dcd3] rounded-full mix-blend-multiply filter blur-3xl opacity-50 animate-blob"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-[#dfd6d1] rounded-full mix-blend-multiply filter blur-3xl opacity-50 animate-blob animation-delay-2000"></div>

      <div className="glass-panel w-full max-w-2xl p-10 rounded-3xl relative z-10 mx-4">
        
        <div className="mb-8 flex items-center justify-between">
          <div className="text-sm font-medium tracking-widest text-stone-400">STEP {step} OF 6</div>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className={`h-1.5 w-8 rounded-full ${i <= step ? 'bg-stone-500' : 'bg-stone-200'}`} />
            ))}
          </div>
        </div>

        <div className="min-h-[300px]">
          <AnimatePresence mode="wait">
            
            {step === 1 && (
              <motion.div key="step1" variants={variants} initial="initial" animate="animate" exit="exit" className="space-y-6">
                <div className="text-center mb-10">
                  <h1 className="text-2xl text-stone-400 mb-2 font-serif italic">साथी</h1>
                  <h2 className="text-4xl font-light text-stone-800 tracking-tight">Welcome to Saathi.</h2>
                  <p className="text-stone-500 mt-2">Your personal AI companion. Let's get you set up.</p>
                </div>
                
                <div>
                  <label className="block text-sm text-stone-500 mb-2">What should Saathi call you?</label>
                  <input 
                    type="text" 
                    name="name" 
                    value={formData.name} 
                    onChange={handleChange}
                    className="w-full bg-white/50 border border-stone-200 rounded-xl px-4 py-3 outline-none focus:border-stone-400 transition-colors"
                    placeholder="Your first name"
                  />
                </div>

                <div>
                  <label className="block text-sm text-stone-500 mb-2">What is your primary role?</label>
                  <div className="grid grid-cols-2 gap-3">
                    {['Student', 'Researcher', 'Both', 'Professional'].map(role => (
                      <button 
                        key={role}
                        onClick={() => setFormData({...formData, role})}
                        className={`py-3 px-4 rounded-xl border text-left transition-all ${formData.role === role ? 'bg-stone-800 text-white border-stone-800' : 'bg-white/50 border-stone-200 text-stone-600 hover:border-stone-300'}`}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div key="step2" variants={variants} initial="initial" animate="animate" exit="exit" className="space-y-6">
                <h2 className="text-3xl font-light text-stone-800 tracking-tight mb-2">Tell Saathi about your work.</h2>
                <p className="text-stone-500 mb-6">This helps me find relevant papers, conferences, and contextualize your daily tasks.</p>
                
                <div>
                  <label className="block text-sm text-stone-500 mb-2">Research interests or subjects (comma-separated)</label>
                  <input 
                    type="text" name="interests" value={formData.interests} onChange={handleChange}
                    className="w-full bg-white/50 border border-stone-200 rounded-xl px-4 py-3 outline-none focus:border-stone-400 transition-colors"
                    placeholder="e.g. reinforcement learning, computational biology"
                  />
                </div>
                
                <div>
                  <label className="block text-sm text-stone-500 mb-2">Your active projects</label>
                  <input 
                    type="text" name="projects" value={formData.projects} onChange={handleChange}
                    className="w-full bg-white/50 border border-stone-200 rounded-xl px-4 py-3 outline-none focus:border-stone-400 transition-colors"
                    placeholder="e.g. Bipedal locomotion paper"
                  />
                </div>

                <div>
                  <label className="block text-sm text-stone-500 mb-2">Institution</label>
                  <input 
                    type="text" name="institutions" value={formData.institutions} onChange={handleChange}
                    className="w-full bg-white/50 border border-stone-200 rounded-xl px-4 py-3 outline-none focus:border-stone-400 transition-colors"
                    placeholder="e.g. Amity University"
                  />
                </div>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div key="step3" variants={variants} initial="initial" animate="animate" exit="exit" className="space-y-6">
                <h2 className="text-3xl font-light text-stone-800 tracking-tight mb-2">Connect your digital life.</h2>
                <p className="text-stone-500 mb-6">Saathi acts on your behalf across your existing tools. Your data never leaves your machine.</p>
                
                <div className="space-y-4">
                  <div className="p-5 border border-stone-200 bg-white/40 rounded-2xl flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-red-50 text-red-500 rounded-full flex items-center justify-center">
                        <Mail size={20} />
                      </div>
                      <div>
                        <h4 className="font-medium text-stone-800">Gmail</h4>
                        <p className="text-sm text-stone-500">Read emails, send replies</p>
                      </div>
                    </div>
                    <button className="px-5 py-2 rounded-full border border-stone-300 text-stone-600 hover:bg-stone-50 transition-colors text-sm font-medium">Connect</button>
                  </div>

                  <div className="p-5 border border-stone-200 bg-white/40 rounded-2xl flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center">
                        <LinkIcon size={20} />
                      </div>
                      <div>
                        <h4 className="font-medium text-stone-800">Google Calendar</h4>
                        <p className="text-sm text-stone-500">Read and create events</p>
                      </div>
                    </div>
                    <button className="px-5 py-2 rounded-full border border-stone-300 text-stone-600 hover:bg-stone-50 transition-colors text-sm font-medium">Connect</button>
                  </div>
                </div>
              </motion.div>
            )}

            {step === 4 && (
              <motion.div key="step4" variants={variants} initial="initial" animate="animate" exit="exit" className="space-y-6">
                <h2 className="text-3xl font-light text-stone-800 tracking-tight mb-2">Ollama Connect</h2>
                <p className="text-stone-500 mb-6">Saathi uses your local hardware to keep your memory entirely private.</p>
                
                <div className="p-6 border border-stone-200 bg-white/40 rounded-2xl text-center">
                  <div className="w-16 h-16 bg-green-50 text-green-500 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Check size={30} />
                  </div>
                  <h3 className="text-lg font-medium text-stone-800 mb-1">Local Inference Engine Detected</h3>
                  <p className="text-stone-500 text-sm">Found instance running at localhost:11434</p>
                  <p className="text-emerald-600 text-sm font-medium mt-2">Active Model: llama3:latest</p>
                </div>
              </motion.div>
            )}

            {step === 5 && (
              <motion.div key="step5" variants={variants} initial="initial" animate="animate" exit="exit" className="space-y-6">
                <h2 className="text-3xl font-light text-stone-800 tracking-tight mb-2">Personality & Behaviour.</h2>
                <p className="text-stone-500 mb-6">How should I interact with you?</p>
                
                <div>
                  <label className="block text-sm text-stone-500 mb-4">How proactive should Saathi be?</label>
                  <div className="space-y-3">
                    {[
                      {id: 'light', label: 'Light', desc: 'Only remind me when I ask'},
                      {id: 'balanced', label: 'Balanced', desc: 'Surface reminders and suggestions daily'},
                      {id: 'proactive', label: 'Proactive', desc: 'Actively check in and nudge frequently'}
                    ].map(opt => (
                      <button 
                        key={opt.id}
                        onClick={() => setFormData({...formData, proactive: opt.id})}
                        className={`w-full p-4 rounded-xl border text-left transition-all flex justify-between items-center ${formData.proactive === opt.id ? 'bg-stone-800 text-white border-stone-800' : 'bg-white/50 border-stone-200 text-stone-600 hover:border-stone-300'}`}
                      >
                        <div>
                          <div className="font-medium">{opt.label}</div>
                          <div className={`text-sm ${formData.proactive === opt.id ? 'text-stone-300' : 'text-stone-500'}`}>{opt.desc}</div>
                        </div>
                        {formData.proactive === opt.id && <Check size={20} />}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {step === 6 && (
              <motion.div key="step6" variants={variants} initial="initial" animate="animate" exit="exit" className="space-y-6">
                <h2 className="text-3xl font-light text-stone-800 tracking-tight mb-2">All set.</h2>
                <p className="text-stone-500 mb-6">Saathi is ready to become your personal companion. Your dashboard is compiling context...</p>
                
                <div className="p-6 bg-stone-800 text-white rounded-2xl">
                  <h3 className="font-medium text-lg mb-4 text-stone-200 font-serif italic">साथी</h3>
                  <p className="text-stone-300 font-light italic text-xl">"I'll remember to remind you gently, help you draft emails in your own voice, and keep an eye on upcoming deadlines so you can focus on the research that matters."</p>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>

        <div className="mt-12 flex justify-between">
          <button 
            onClick={prevStep}
            className={`flex items-center text-stone-500 hover:text-stone-800 px-4 py-2 transition-opacity ${step === 1 ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
          >
            <ChevronLeft size={20} className="mr-1" /> Back
          </button>
          
          {step < 6 ? (
            <button 
              onClick={nextStep}
              className="bg-stone-800 text-white px-8 py-3 rounded-full flex items-center hover:bg-stone-700 transition-colors shadow-lg shadow-stone-200"
            >
              Continue <ChevronRight size={20} className="ml-1" />
            </button>
          ) : (
            <button 
              onClick={handleFinish}
              className="bg-emerald-600 text-white px-8 py-3 rounded-full flex items-center hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-200"
            >
              Open Dashboard <ChevronRight size={20} className="ml-1" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
